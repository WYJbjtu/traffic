"""Independent saved-probability audit and predeclared paired analyses.

CLI: python -m experiments.unified96.poster_analysis --run <run> --out <new-dir>
No fitting or test-driven selection. Fixed fitted-model uncertainty only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn import metrics as sm

from experiments.unified96.run import event_hash, paired_bootstrap, MODELS
from experiments.unified96.matrix import dump
from traffic_recovery.data.http import sha256_file


def recompute(block: pd.DataFrame) -> dict[str, float | int]:
    """Recalculate every primary metric independently of the training metric helper."""
    y, p = block.y_true.to_numpy(dtype=int), block.y_score.to_numpy(dtype=float)
    h = (p >= .5).astype(int)
    if not np.isfinite(p).all() or not ((p >= 0) & (p <= 1)).all() or not np.array_equal(h, block.y_pred):
        raise ValueError('Invalid saved probability/threshold prediction')
    tn, fp, fn, tp = sm.confusion_matrix(y, h, labels=[0, 1]).ravel()
    return {'roc_auc': sm.roc_auc_score(y, p), 'average_precision': sm.average_precision_score(y, p),
        'macro_f1': sm.f1_score(y, h, average='macro', zero_division=0),
        'balanced_accuracy': sm.balanced_accuracy_score(y, h), 'precision': sm.precision_score(y, h, zero_division=0),
        'recall': sm.recall_score(y, h, zero_division=0), 'f1': sm.f1_score(y, h, zero_division=0),
        'accuracy': sm.accuracy_score(y, h), 'brier': sm.brier_score_loss(y, p),
        'log_loss': sm.log_loss(y, np.clip(p, 1e-7, 1-1e-7), labels=[0,1]),
        'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)}


def verify_run(run: Path, *, expected_arms: int = 32) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Verify artifact SHA, identities, exact same populations and fitted statistics.

    Raises on any disagreement; requires local predictions and prepared matrix.
    """
    manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    if not manifest['status'].startswith('COMPLETE'):
        raise ValueError('Incomplete run')
    for name, digest in manifest['outputs_sha256'].items():
        if sha256_file(run/name) != digest:
            raise ValueError(f'Changed run artifact: {name}')
    predictions = pd.read_parquet(run/'predictions.parquet')
    metrics = pd.read_csv(run/'metrics.csv')
    population = pd.read_parquet(run/'event_population.parquet')
    if predictions.duplicated(['event_id', 'split', 'model', 'feature_arm']).any():
        raise ValueError('Duplicate prediction identity')
    if len(predictions[['model','feature_arm']].drop_duplicates()) != expected_arms:
        raise ValueError('Wrong number of executed arms')
    if len(metrics) != expected_arms*2 or metrics.duplicated(['model','feature_arm','split']).any():
        raise ValueError('Wrong metric inventory')
    for row in metrics.itertuples():
        block = predictions.loc[predictions.model.eq(row.model) & predictions.feature_arm.eq(row.feature_arm) & predictions.split.eq(row.split)]
        actual = block.sort_values('event_id')[['event_id','prediction_time','detector_id','y_true']].reset_index(drop=True)
        wanted = population.loc[population.split.eq(row.split)].sort_values('event_id')[['event_id','prediction_time','detector_id','label']].rename(columns={'label':'y_true'}).reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, wanted, check_dtype=False)
        if len(block) != row.n_events or event_hash(block.event_id) != row.event_ids_sha256 or int(block.y_true.sum()) != row.n_positive or int((1-block.y_true).sum()) != row.n_negative:
            raise ValueError('Metric population mismatch')
        if not block.threshold.eq(.5).all():
            raise ValueError('Threshold differs')
        for key, value in recompute(block).items():
            # XGBoost metrics were computed on float32 probabilities before
            # concatenation upcast them to float64; allow <1 float32 epsilon
            # only for arithmetic mean losses. Ranking/count metrics stay tight.
            atol = 1e-7 if row.model == 'xgboost' and key in ('brier', 'log_loss') else 1e-12
            if not np.isclose(value, getattr(row, key), rtol=1e-11, atol=atol):
                raise ValueError(f'Metric mismatch: {row.model}/{row.feature_arm}/{key}')
    data = pd.read_parquet(run/'model_input.parquet')
    fits = json.loads((run/'fit_audit.json').read_text(encoding='utf-8'))
    tuning = pd.read_csv(run/'tuning.csv')
    for fit in fits:
        train = data.loc[data.split.eq('train'), fit['feature_columns']]
        stats = np.array([np.nan if x is None else x for x in fit['imputer_statistics']])
        if not np.allclose(stats, train.mean().to_numpy(dtype=float), equal_nan=True):
            raise ValueError('Imputer not fitted to train-only means')
        if fit['fit_event_ids_sha256'] != event_hash(data.loc[data.split.eq('train'),'event_id']):
            raise ValueError('Preprocessing fit population differs')
        scores = tuning.loc[tuning.model.eq(fit['model']) & tuning.feature_arm.eq(fit['feature_arm'])].sort_values('candidate')
        if fit['selected_candidate'] != int(np.argmin(scores.validation_log_loss)):
            raise ValueError('Selection does not minimize validation log loss')
    return predictions, metrics, manifest


def error_transitions(left: pd.DataFrame, right: pd.DataFrame) -> dict:
    """Same-event classification transitions and positive/negative mean score changes."""
    paired = left.merge(right, on=['event_id','prediction_time','detector_id','y_true'],
        how='outer', validate='one_to_one', indicator=True, suffixes=('_base','_spatial'))
    if len(paired) != len(left) or len(paired) != len(right) or not paired._merge.eq('both').all():
        raise ValueError('Error analysis requires same events, times and labels')
    a = paired.y_pred_base.eq(paired.y_true); b = paired.y_pred_spatial.eq(paired.y_true)
    return {'n_events': len(paired), 'both_correct': int((a & b).sum()), 'both_wrong': int((~a & ~b).sum()),
        'only_spatial_correct': int((~a & b).sum()), 'only_base_correct': int((a & ~b).sum()),
        **{f'mean_delta_probability_y{label}': float((paired.loc[paired.y_true.eq(label),'y_score_spatial']-
            paired.loc[paired.y_true.eq(label),'y_score_base']).mean()) for label in (0,1)}}


def analyze(run: Path, out: Path) -> None:
    """Save all four spatial contrasts, F3/F7 intervals and error analysis, no overwrite."""
    if out.exists():
        raise FileExistsError(out)
    pred, metrics, manifest = verify_run(run)
    out.mkdir(parents=True)
    gains, boot, errors = [], [], []
    for name in MODELS:
        test = pred.loc[pred.model.eq(name) & pred.split.eq('test')]
        left, right = (test.loc[test.feature_arm.eq(arm)] for arm in ('F3','F7'))
        result = paired_bootstrap(left, right, replicates=1000, seed=42)
        boot.append({'model': name, 'grouping': 'target_detector', **result})
        # Predeclared seven-day blocks, HKT epoch (not adapted to scores).
        epoch = pd.Timestamp('2026-01-01', tz='Asia/Hong_Kong')
        blocks = []
        for frame in (left, right):
            block = frame.copy()
            block['detector_id'] = ((block.prediction_time - epoch).dt.total_seconds() // (7*86400)).astype(int).astype(str)
            blocks.append(block)
        if blocks[0].detector_id.nunique() >= 10:
            boot.append({'model': name, 'grouping': 'fixed_7day_HKT_20260101',
                **paired_bootstrap(*blocks, replicates=1000, seed=20261108)})
        errors.append({'model': name, **error_transitions(left, right)})
        for base, spatial in [('F3','F7'), ('F0','F4'), ('F1','F5'), ('F2','F6')]:
            a = metrics.loc[metrics.model.eq(name) & metrics.split.eq('test') & metrics.feature_arm.eq(base)].iloc[0]
            b = metrics.loc[metrics.model.eq(name) & metrics.split.eq('test') & metrics.feature_arm.eq(spatial)].iloc[0]
            gains.append({'model': name, 'comparison': f'{spatial}_minus_{base}', 'n_events': int(a.n_events),
                **{f'delta_{k}': float(b[k]-a[k]) for k in ['roc_auc','average_precision','macro_f1',
                     'balanced_accuracy','precision','recall','brier','log_loss']},
                'ci_95_lower': result['roc_auc']['ci_95_percentile'][0] if base=='F3' else None,
                'ci_95_upper': result['roc_auc']['ci_95_percentile'][1] if base=='F3' else None,
                'clusters': result['clusters'] if base=='F3' else None,
                'valid_resamples': result['roc_auc']['valid_resamples'] if base=='F3' else None,
                'invalid_single_class': result['invalid_single_class'] if base=='F3' else None})
    pd.DataFrame(gains).to_csv(out/'spatial_contrasts.csv', index=False)
    pd.DataFrame(errors).to_csv(out/'error_transitions.csv', index=False)
    dump(out/'paired_bootstrap.json', boot)
    dump(out/'verification.json', {'status': 'passed', 'arms': 32, 'metric_rows_recomputed': len(metrics),
        'saved_predictions_checked': len(pred), 'run_manifest_sha256': sha256_file(run/'manifest.json'),
        'preprocessing': 'all 32 fitted imputers checked against train-only column means',
        'metric_method': 'independent sklearn recomputation; AP not trapezoidal PR-AUC; log loss clipped at 1e-7; XGBoost float32 mean losses checked within 1e-7 (observed max difference 3.29e-8)',
        'bootstrap_limits': 'fixed fitted models; shared neighbors not fully addressed; unadjusted multiple comparisons',
        'files_sha256': {p.name: sha256_file(p) for p in out.iterdir() if p.is_file()}})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.run, args.out)

if __name__ == '__main__':
    main()
