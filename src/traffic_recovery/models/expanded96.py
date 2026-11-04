"""Exploratory, frozen 96-lane recovery-confirmation benchmark (not target approval).

Input: verified expanded96 Release events and 5-minute bins, never old pilot data.
Output: new directory with hashed prediction, metric and evidence artifacts.
All historical bins must be usable and available no later than event prediction time.
No future outcome, reason or source quality report is admitted as a feature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, confusion_matrix, f1_score, log_loss, precision_score, recall_score,
    roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from traffic_recovery.data.http import sha256_file

EXPECTED = {
    'events': 'd9cd1c0ede22d4f919e3b3a7ece9fab25a8646e3f5ee8b2fb0f4ff900606e570',
    'bins': '2936bb58bac7a87e4d8d986165158a39d148dc62065d2a095713fcf4e7ea7de8',
}
UNIT = ['detector_id', 'direction', 'lane_id']
LOCAL = ['speed_kmh', 'speed_ratio', 'baseline_kmh', 'valid_slots', 'onset_observed_minutes']
HISTORY = ['lag_5m_ratio', 'lag_10m_ratio', 'lag_15m_ratio', 'lag_30m_ratio',
           'history_mean_ratio', 'history_trend_ratio', 'history_observed_bins']


def history_features(events: pd.DataFrame, bins_path: Path) -> pd.DataFrame:
    """Extract strictly past, independently available speed history per event.

    Unobserved lag values stay null. ``history_observed_bins`` counts usable bins
    including the onset confirmation, among the seven requested 5-minute slots.
    """
    groups = {key: frame for key, frame in events.groupby(UNIT)}
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict] = []
    parquet = pq.ParquetFile(bins_path)
    for rg in range(parquet.num_row_groups):
        chunk = parquet.read_row_group(rg, columns=UNIT + ['timestamp', 'speed_kmh', 'usable',
            'available_at', 'last_source_available_at']).to_pandas()
        for key, frame in chunk.groupby(UNIT, sort=False):
            if key not in groups:
                continue
            if key in seen:
                raise ValueError('Bin unit spans row groups; abort instead of losing history')
            seen.add(key)
            frame = frame.set_index('timestamp', verify_integrity=True).sort_index()
            for event in groups[key].itertuples(index=False):
                times = [event.onset_confirmed_at - pd.Timedelta(minutes=i) for i in (0, 5, 10, 15, 20, 25, 30)]
                window = frame.reindex(times)
                valid = (window.usable.astype('boolean').fillna(False).astype(bool) & window.speed_kmh.notna()
                         & window.available_at.le(event.prediction_time)
                         & window.last_source_available_at.le(event.prediction_time))
                ratios = window.speed_kmh.where(valid).to_numpy(dtype=float) / event.baseline_kmh
                rows.append({'event_id': event.event_id, 'lag_5m_ratio': ratios[1],
                    'lag_10m_ratio': ratios[2], 'lag_15m_ratio': ratios[3],
                    'lag_30m_ratio': ratios[6], 'history_mean_ratio': float(np.nanmean(ratios)) if valid.any() else np.nan,
                    'history_trend_ratio': ratios[0] - ratios[3],
                    'history_observed_bins': int(valid.sum()),
                    'history_latest_available_at': window.available_at.where(valid).max()})
    result = pd.DataFrame(rows)
    if len(result) != len(events) or not result.event_id.is_unique or set(result.event_id) != set(events.event_id):
        raise ValueError('History/event identity mismatch')
    return result


def metrics(y: np.ndarray, prob: np.ndarray, pred: np.ndarray) -> dict:
    cm = confusion_matrix(y, pred, labels=[0, 1])
    return {'accuracy': accuracy_score(y, pred), 'precision': precision_score(y, pred, zero_division=0),
        'recall': recall_score(y, pred, zero_division=0), 'f1': f1_score(y, pred, zero_division=0),
        'macro_f1': f1_score(y, pred, average='macro', zero_division=0),
        'balanced_accuracy': balanced_accuracy_score(y, pred),
        'roc_auc': roc_auc_score(y, prob) if len(np.unique(y)) == 2 else None,
        'average_precision': average_precision_score(y, prob) if len(np.unique(y)) == 2 else None,
        'brier': brier_score_loss(y, prob), 'log_loss': log_loss(y, np.clip(prob, 1e-7, 1-1e-7), labels=[0, 1]),
        'tn': int(cm[0, 0]), 'fp': int(cm[0, 1]), 'fn': int(cm[1, 0]), 'tp': int(cm[1, 1])}


def candidate_models() -> dict:
    """Small predeclared budget; validation log loss selects two candidates/model."""
    return {
        'logistic_regression': [make_pipeline(SimpleImputer(add_indicator=True), StandardScaler(),
            LogisticRegression(C=c, max_iter=1000, random_state=42)) for c in (0.1, 1.0)],
        'decision_tree': [make_pipeline(SimpleImputer(add_indicator=True),
            DecisionTreeClassifier(max_depth=d, min_samples_leaf=50, random_state=42)) for d in (4, 8)],
        'random_forest': [make_pipeline(SimpleImputer(add_indicator=True),
            RandomForestClassifier(n_estimators=100, max_depth=d, min_samples_leaf=20, n_jobs=2,
                                   random_state=42)) for d in (6, 10)],
        'xgboost': [make_pipeline(SimpleImputer(add_indicator=True),
            XGBClassifier(n_estimators=150, max_depth=d, learning_rate=0.05, n_jobs=2,
                          tree_method='hist', random_state=42, eval_metric='logloss')) for d in (3, 5)],
        'hist_gradient_boosting': [make_pipeline(SimpleImputer(add_indicator=True),
            HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=n, random_state=42)) for n in (15, 31)],
    }


def run(events_path: Path, bins_path: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f'Refusing overwrite: {output}')
    for path, key in ((events_path, 'events'), (bins_path, 'bins')):
        if sha256_file(path) != EXPECTED[key]:
            raise ValueError(f'Expanded96 Release hash mismatch: {path}')
    events = pd.read_parquet(events_path)
    if (len(events) != 30452 or events.event_id.duplicated().any()
            or not 1 <= events[UNIT].drop_duplicates().shape[0] <= 96
            or events.split_proposal.value_counts().to_dict() != {'train': 14290, 'validation': 8557, 'test': 7605}
            or not events.feature_max_available_at.le(events.prediction_time).all()
            or not events.definition_version.eq(events.definition_version.iloc[0]).all()):
        raise ValueError('Expanded96 cohort identity/availability mismatch')
    history = history_features(events, bins_path)
    events = events.merge(history, on='event_id', validate='one_to_one')
    assert events.history_latest_available_at.dropna().le(events.loc[events.history_latest_available_at.notna(), 'prediction_time']).all()
    output.mkdir(parents=True)
    history.to_parquet(output / 'history_features.parquet', index=False)
    results = []
    predictions = []
    tuning = []
    for horizon in (30, 15, 60):
        label = f'label_{horizon}m'
        for feature_set, columns in (('A1_local', LOCAL), ('A2_local_history', LOCAL + HISTORY)):
            known = events[label].notna()
            train = events.split_proposal.eq('train') & known
            val = events.split_proposal.eq('validation') & known
            test = events.split_proposal.eq('test') & known
            x_train = events.loc[train, columns].to_numpy(dtype=float)
            y_train = events.loc[train, label].to_numpy(dtype=int)
            x_val = events.loc[val, columns].to_numpy(dtype=float)
            y_val = events.loc[val, label].to_numpy(dtype=int)
            if len(set(y_train)) != 2 or len(set(y_val)) != 2:
                raise ValueError('Training/validation needs both label classes')
            prevalence = float(y_train.mean())
            models = candidate_models()
            selected = {}
            for name, candidates in models.items():
                scores = []
                for i, model in enumerate(candidates):
                    model.fit(x_train, y_train)
                    score = log_loss(y_val, np.clip(model.predict_proba(x_val)[:, 1], 1e-7, 1-1e-7), labels=[0,1])
                    scores.append(float(score))
                    tuning.append({'horizon_min': horizon, 'feature_set': feature_set, 'model': name,
                        'candidate': i, 'validation_log_loss': score})
                idx = int(np.argmin(scores))
                selected[name] = (candidates[idx], idx)
            for split, mask in (('validation', val), ('test', test)):
                subset = events.loc[mask]
                x = subset[columns].to_numpy(dtype=float)
                y = subset[label].to_numpy(dtype=int)
                for name in ('majority_class', 'train_prevalence', 'speed_trend_rule', *selected):
                    baseline = name in ('majority_class', 'train_prevalence', 'speed_trend_rule')
                    if baseline and feature_set != 'A1_local':
                        continue  # A0 is evaluated once on precisely the same event IDs.
                    reported_set = 'A0_baseline' if baseline else feature_set
                    if name == 'majority_class':
                        prob = np.full(len(subset), float(prevalence >= 0.5))
                        pred = (prob >= 0.5).astype(int)
                    elif name == 'train_prevalence':
                        prob = np.full(len(subset), prevalence)
                        pred = (prob >= 0.5).astype(int)
                    elif name == 'speed_trend_rule':
                        # Predeclared: improving speed over preceding 15 minutes => recovery.
                        # Unknown history is not interpreted as improvement.
                        prob = (subset.history_trend_ratio > 0).fillna(False).to_numpy(dtype=float)
                        pred = prob.astype(int)
                    else:
                        prob = selected[name][0].predict_proba(x)[:, 1]
                        pred = (prob >= 0.5).astype(int)
                    row = {'horizon_min': horizon, 'target': 'recovery_confirmation_v1',
                        'feature_set': reported_set, 'split': split, 'model': name,
                        'n_known': len(subset), 'n_unknown': int((events.split_proposal.eq(split) & ~known).sum()),
                        'n_positive': int(y.sum()), 'features': '|'.join(columns),
                        'selected_candidate': selected[name][1] if name in selected else None,
                        **metrics(y, prob, pred)}
                    results.append(row)
                    predictions.append(pd.DataFrame({'event_id': subset.event_id, 'split': split,
                        'horizon_min': horizon, 'feature_set': reported_set, 'model': name,
                        'label': y, 'probability': prob, 'prediction': pred}))
    pd.DataFrame(results).to_csv(output / 'model_metrics.csv', index=False)
    pd.DataFrame(tuning).to_csv(output / 'tuning.csv', index=False)
    pd.concat(predictions, ignore_index=True).to_parquet(output / 'predictions.parquet', index=False)
    manifest = {'status': 'EXPLORATORY — target and lane identity pending team approval',
        'dataset': 'expanded96-long-window-v1', 'target': 'recovery_confirmation_v1',
        'source_sha256': EXPECTED, 'events': len(events), 'frozen_lane_units': 96,
        'event_lane_units': int(events[UNIT].drop_duplicates().shape[0]),
        'splits': {'train': 14290, 'validation': 8557, 'test': 7605},
        'feature_sets': {'A1_local': LOCAL, 'A2_local_history': LOCAL + HISTORY},
        'seed': 42, 'decision_threshold': 0.5, 'selection': 'minimum validation log loss; no refit',
        'model_budget': 'two fixed candidates per supervised algorithm; see candidate_models source and tuning.csv',
        'split_boundaries': {'train': '2023-02 through 2024', 'validation': '2025',
                             'test': '2026-01 through 2026-09'},
        'history_policy': 'usable bins; bin timestamp and source availability <= prediction_time; no interpolation',
        'python': platform.python_version(), 'sklearn': sklearn.__version__,
        'xgboost': __import__('xgboost').__version__, 'outputs_sha256': {
            name: sha256_file(output / name) for name in
            ('history_features.parquet', 'predictions.parquet', 'model_metrics.csv', 'tuning.csv')}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--bins', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    run(a.events, a.bins, a.output)


if __name__ == '__main__':
    main()
