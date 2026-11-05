"""Offline verification of the shared 2026-11-01 real-data rerun."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from traffic_recovery.models.evaluation import evaluate_predictions
from traffic_recovery.models.artifact_integrity import verify_manifest_files


def verify(*, strict_snapshot: bool = False) -> dict[str, object]:
    """Verify included artifacts and paired results without raw data or training."""
    base = Path(__file__).resolve().parent
    result = base / 'rerun_20261101'
    checks = 0

    def check(condition: object, message: str) -> None:
        nonlocal checks
        if not bool(condition):
            raise AssertionError(message)
        checks += 1

    manifest = json.loads((base / 'share_manifest.json').read_text(encoding='utf-8'))
    integrity = verify_manifest_files(
        ROOT, manifest['sha256'],
        immutable_prefixes=('experiments/tianhao/results', 'experiments/tianhao/rerun_20261101'),
        strict_snapshot=strict_snapshot,
    )
    checks += integrity['verified_artifacts']
    pred = pd.read_parquet(result / 'predictions.parquet')
    old = pd.read_parquet(base / 'results/predictions.parquet')
    keys = ['model', 'feature_set', 'split', 'event_id', 'horizon_min']
    comparable = keys + ['prediction_time', 'y_true', 'y_pred', 'y_score', 'score_kind']
    pd.testing.assert_frame_equal(pred[comparable].sort_values(keys).reset_index(drop=True),
                                  old[comparable].sort_values(keys).reset_index(drop=True))
    check(len(pred) == 95186, 'Prediction count and agreement with historical run')
    check(pred.horizon_min.eq(30).all(), 'Only the declared 30-minute task')
    check(pred.groupby(['model', 'feature_set']).ngroups == 14, '14 paired arms')
    table = pd.read_csv(result / 'metrics_summary.csv').set_index(['model', 'feature_set', 'split'])
    cm = pd.read_csv(result / 'confusion_matrices.csv').set_index(['model', 'feature_set', 'split'])
    for split, expected in [('train', 3428), ('validation', 2008), ('test', 1363)]:
        reference = None
        for _, arm in pred.loc[pred.split.eq(split)].groupby(['model', 'feature_set']):
            check(len(arm) == expected and arm.event_id.is_unique, 'Unique cohort: ' + split)
            identifiers = set(arm.event_id)
            check(reference is None or reference == identifiers, 'Paired cohort: ' + split)
            reference = identifiers
    for row in evaluate_predictions(pred, version_column='experiment_version').itertuples():
        check(np.isclose(table.loc[(row.model, row.feature_set, row.split), row.metric_name],
                         row.metric_value, equal_nan=True), 'Recomputed metric: ' + row.metric_name)
    for group, part in pred.groupby(['model', 'feature_set', 'split']):
        check(np.array_equal(cm.loc[group, ['tn', 'fp', 'fn', 'tp']].to_numpy(),
                             confusion_matrix(part.y_true, part.y_pred, labels=[0, 1]).ravel()), 'Confusion counts')
    # The historical 22-cell Notebook is intentionally removed, not rebranded as
    # a 96-lane run; verify only the current publication's renderable output here.
    notebook = json.loads((ROOT / 'notebooks/Tianhao_新版96车道_完整重跑_20261104.ipynb').read_text(encoding='utf-8'))
    code = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    check([c['execution_count'] for c in code] == list(range(1, 11)), '10 executed canonical code cells')
    check(not any(o.get('output_type') == 'error' for c in code for o in c.get('outputs', [])), 'No canonical notebook errors')
    check(sum('image/png' in o.get('data', {}) for c in code for o in c.get('outputs', [])) == 7, '7 canonical embedded figures')
    return {'status': 'passed', 'checks': checks, 'prediction_rows': len(pred), 'arms': 14, 'integrity': integrity,
            'note': 'Offline consistency checks only; no scientific approval or independent new test cohort.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict-snapshot', action='store_true', help='Reject recorded source/document drift as well as artifact changes.')
    args = parser.parse_args()
    print(json.dumps(verify(strict_snapshot=args.strict_snapshot), indent=2))
