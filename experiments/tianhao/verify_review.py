"""Offline verification of the deliberately small, committed review package."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, confusion_matrix
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from traffic_recovery.models.evaluation import evaluate_predictions
from traffic_recovery.models.artifact_integrity import verify_manifest_files
RESULTS = Path(__file__).resolve().parent / 'results'

def verify(*, strict_snapshot=False):
    checks = 0
    def check(condition, description):
        nonlocal checks
        if not bool(condition):
            raise AssertionError(description)
        checks += 1
    provenance = json.loads((RESULTS / 'provenance.json').read_text(encoding='utf-8'))
    for name, expected in provenance['included_historical_outputs'].items():
        with (RESULTS / name).open('rb') as stream:
            check(hashlib.file_digest(stream, 'sha256').hexdigest() == expected, 'Original output SHA256: ' + name)
    pred = pd.read_parquet(RESULTS / 'predictions.parquet')
    table = pd.read_csv(RESULTS / 'metrics_summary.csv').set_index(['model', 'feature_set', 'split'])
    cm = pd.read_csv(RESULTS / 'confusion_matrices.csv').set_index(['model', 'feature_set', 'split'])
    check(len(pred) == 95186, 'Prediction row count')
    check(pred.groupby(['model', 'feature_set']).ngroups == 14, 'Four baselines plus ten fitted arms')
    check(pred.horizon_min.eq(30).all(), 'Only 30-minute predictions')
    cohort = pd.read_csv(RESULTS / 'cohort_summary.csv').set_index('split')
    for split, n in [('train', 3428), ('validation', 2008), ('test', 1363)]:
        arms = list(pred.loc[pred.split.eq(split)].groupby(['model', 'feature_set']))
        reference = arms[0][1].set_index('event_id').sort_index()
        check(len(reference) == n == cohort.at[split, 'known'], 'Known cohort count: ' + split)
        for _, part in arms:
            check(part.event_id.is_unique and set(part.event_id) == set(reference.index), 'Paired unique cohort: ' + split)
            ordered = part.set_index('event_id').sort_index()
            check(ordered.y_true.equals(reference.y_true) and ordered.prediction_time.equals(reference.prediction_time), 'Consistent labels/times across arms')
        # Prove temporal boundaries directly from saved predictions.
        times = reference.prediction_time
        start, end = {'train': ('2023-02-01', '2025-01-01'), 'validation': ('2025-01-01', '2026-01-01'), 'test': ('2026-01-01', '2026-10-01')}[split]
        check(times.ge(pd.Timestamp(start, tz='Asia/Hong_Kong')).all() and times.lt(pd.Timestamp(end, tz='Asia/Hong_Kong')).all(), 'Temporal split: ' + split)
    recomputed = evaluate_predictions(pred, version_column='experiment_version')
    for row in recomputed.itertuples():
        actual = table.loc[(row.model, row.feature_set, row.split), row.metric_name]
        check(np.isclose(actual, row.metric_value, equal_nan=True), 'Recompute ' + row.metric_name)
    for keys, part in pred.groupby(['model', 'feature_set', 'split']):
        check(np.isclose(table.loc[keys, 'macro_f1'], f1_score(part.y_true, part.y_pred, average='macro', labels=[0, 1], zero_division=0)), 'Macro-F1')
        check(np.array_equal(cm.loc[keys, ['tn', 'fp', 'fn', 'tp']].to_numpy(), confusion_matrix(part.y_true, part.y_pred, labels=[0, 1]).ravel()), 'Confusion matrix')
    # Historical Notebook hashes remain in the frozen manifest; the removed file
    # cannot be silently treated as a verified current artifact.
    notebook = ROOT / 'notebooks/Tianhao_新版96车道_完整重跑_20261104.ipynb'
    cells = json.loads(notebook.read_text(encoding='utf-8'))['cells']
    check(not any(o.get('output_type') == 'error' for c in cells for o in c.get('outputs', [])), 'Canonical Notebook contains no error output')
    package_manifest = RESULTS / 'package_manifest.json'
    integrity = None
    if package_manifest.exists():
        integrity = verify_manifest_files(
            ROOT, json.loads(package_manifest.read_text(encoding='utf-8'))['sha256'],
            immutable_prefixes=('experiments/tianhao/results', 'experiments/tianhao/rerun_20261101'),
            strict_snapshot=strict_snapshot,
        )
        checks += integrity['verified_artifacts']
    return {'status': 'passed', 'checks': checks, 'prediction_rows': len(pred), 'arms': 14, 'integrity': integrity, 'note': 'Offline output checks only; source-time checks remain in the historical real-run verification. No scientific approval.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-report', action='store_true')
    parser.add_argument('--strict-snapshot', action='store_true', help='Reject recorded source/document drift as well as artifact changes.')
    args = parser.parse_args()
    result = verify(strict_snapshot=args.strict_snapshot)
    if args.write_report:
        (RESULTS / 'review_validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
