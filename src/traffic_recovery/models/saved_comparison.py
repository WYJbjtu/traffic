"""Recompute metrics on saved predictions without fitting, tuning or pooling runs."""
from __future__ import annotations

from itertools import combinations
from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from .evaluation import evaluate_predictions

ARM = ['horizon_min', 'feature_set', 'model', 'split']


def normalise_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate one saved run and coalesce legacy feature-count column names.

    Unknown labels must already be excluded from prediction rows. Duplicate event
    predictions, naive times, invalid labels and nonfinite scores raise explicitly.
    Non-probability rule scores may lie outside [0,1]. Input is never modified.
    """
    required = {*ARM, 'event_id', 'prediction_time', 'y_true', 'y_pred', 'y_score',
                'score_kind', 'n_censored_in_split'}
    if required - set(frame):
        raise ValueError(f'Missing saved prediction columns: {sorted(required - set(frame))}')
    result = frame.copy()
    if result.empty or result[ARM + ['event_id']].isna().any().any():
        raise ValueError('Saved predictions need non-null arm/event keys and at least one row')
    if not result.event_id.map(lambda x: isinstance(x, str) and bool(x.strip())).all():
        raise ValueError('event_id must be a nonempty string')
    if result.duplicated(ARM + ['event_id']).any():
        raise ValueError('Duplicate event prediction within an arm')
    if not isinstance(result.prediction_time.dtype, pd.DatetimeTZDtype) or result.prediction_time.isna().any():
        raise ValueError('prediction_time must be non-null timezone-aware timestamps')
    result['prediction_time'] = result.prediction_time.dt.tz_convert('Asia/Hong_Kong')
    if result.groupby('event_id')[['prediction_time', 'split']].nunique().gt(1).any().any():
        raise ValueError('An event changes prediction time or split within a saved run')
    if not result.y_true.isin([0, 1]).all() or not result.y_pred.isin([0, 1]).all():
        raise ValueError('Saved labels and decisions must be known binary values')
    score = pd.to_numeric(result.y_score, errors='raise')
    if not np.isfinite(score.to_numpy(dtype=float)).all():
        raise ValueError('Prediction scores must be finite')
    if not result.score_kind.isin(['probability', 'rule_score']).all():
        raise ValueError('Unknown score semantics')
    if not score.loc[result.score_kind.eq('probability')].between(0, 1).all():
        raise ValueError('Probability scores must lie in [0,1]')
    counts = pd.Series(np.nan, index=result.index)
    for column in ['n_missing_feature_in_split', 'n_missing_rule_feature_in_split']:
        if column in result:
            counts = counts.fillna(pd.to_numeric(result[column], errors='raise'))
    for name, values in [('n_missing_feature_in_split', counts),
                         ('n_censored_in_split', pd.to_numeric(result.n_censored_in_split, errors='raise'))]:
        if values.isna().any() or not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
            raise ValueError(f'{name} needs nonnegative integer counts')
        result[name] = values.astype(int)
    for name in ['n_missing_feature_in_split', 'n_censored_in_split', 'score_kind']:
        if result.groupby(ARM, dropna=False)[name].nunique().gt(1).any():
            raise ValueError(f'Conflicting per-arm metadata: {name}')
    return result


def compare_saved_runs(
    frames: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return wide metrics, confusion counts and cross-run pairing audit.

    Rows retain experiment/model/features/horizon/split identity. Every arm sharing
    a horizon and split must use identical event IDs, labels and prediction times,
    within each run and across runs. Mismatches fail before a comparison is emitted.
    Different feature sets are retained separately, never merged into a ranking.
    """
    if not frames:
        raise ValueError('At least one saved run is required')
    normalised = {name: normalise_predictions(frame) for name, frame in frames.items()}
    cohorts: dict[tuple[int, str], tuple[str, pd.DataFrame]] = {}
    for name, frame in normalised.items():
        for keys, arm in frame.groupby(ARM, sort=True):
            horizon, features, model, split = keys
            cohort_key = (horizon, split)
            ordered = arm.set_index('event_id').sort_index()
            if cohort_key not in cohorts:
                cohorts[cohort_key] = (name, ordered)
                continue
            ref_name, ref = cohorts[cohort_key]
            if not ordered.index.equals(ref.index):
                raise ValueError(f'Event cohort mismatch: {name}/{features}/{model}/{horizon}/{split} vs {ref_name}')
            if not np.array_equal(ordered.y_true, ref.y_true):
                raise ValueError(f'Label mismatch: {name}/{horizon}/{split}')
            if not ordered.prediction_time.equals(ref.prediction_time):
                raise ValueError(f'Prediction-time mismatch: {name}/{horizon}/{split}')
    metric_tables = []
    confusion_rows = []
    for name, frame in normalised.items():
        frame['_comparison_version'] = 'saved-prediction-comparison-v1'
        long = evaluate_predictions(frame, version_column='_comparison_version')
        wide = long.pivot(index=ARM, columns='metric_name', values='metric_value').reset_index()
        counts = long.groupby(ARM, sort=True)[['n_rows', 'n_events', 'n_positive', 'n_censored', 'n_missing_feature']].first().reset_index()
        wide = wide.merge(counts, on=ARM, validate='one_to_one')
        wide.insert(0, 'experiment', name)
        wide['n_negative'] = wide.n_rows - wide.n_positive
        metric_tables.append(wide)
        for keys, arm in frame.groupby(ARM, sort=True):
            tn, fp, fn, tp = confusion_matrix(arm.y_true, arm.y_pred, labels=[0, 1]).ravel()
            confusion_rows.append({'experiment': name, **dict(zip(ARM, keys)),
                                   'n_rows': len(arm), 'n_events': arm.event_id.nunique(),
                                   'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)})
    pair_rows = []
    for left, right in combinations(normalised, 2):
        a = {key: group for key, group in normalised[left].groupby(ARM)}
        b = {key: group for key, group in normalised[right].groupby(ARM)}
        for key in sorted(a.keys() & b.keys()):
            x = a[key].set_index('event_id').sort_index()
            y = b[key].set_index('event_id').sort_index()
            pair_rows.append({'left_experiment': left, 'right_experiment': right,
                              **dict(zip(ARM, key)), 'n_left': len(x), 'n_right': len(y),
                              'identical_events_labels_times': True,
                              'max_score_difference': float(np.abs(x.y_score - y.y_score).max()),
                              'decision_disagreements': int(x.y_pred.ne(y.y_pred).sum())})
    metrics = pd.concat(metric_tables, ignore_index=True).sort_values(['experiment', *ARM]).reset_index(drop=True)
    pair_columns = ['left_experiment', 'right_experiment', *ARM, 'n_left', 'n_right',
                    'identical_events_labels_times', 'max_score_difference', 'decision_disagreements']
    return metrics, pd.DataFrame(confusion_rows), pd.DataFrame(pair_rows, columns=pair_columns)
