"""Synthetic saved predictions test pairing and metric recomputation, not science."""
import pandas as pd
import pytest
from sklearn.metrics import f1_score

from traffic_recovery.models.saved_comparison import compare_saved_runs


def predictions():
    return pd.DataFrame({
        'event_id': ['SYNTHETIC-1', 'SYNTHETIC-2', 'SYNTHETIC-3', 'SYNTHETIC-4'],
        'prediction_time': pd.date_range('2026-01-01', periods=4, freq='2h', tz='Asia/Hong_Kong'),
        'model': 'synthetic', 'feature_set': 'local', 'horizon_min': 30, 'split': 'test',
        'y_true': [0, 0, 0, 1], 'y_pred': 0, 'y_score': 0.25, 'score_kind': 'probability',
        'n_censored_in_split': 2, 'n_missing_rule_feature_in_split': 0,
    })


def test_recomputed_macro_confusion_counts_and_different_scores_remain_separate():
    left = predictions()
    right = predictions().assign(y_score=0.3)
    metrics, cm, pairs = compare_saved_runs({'left': left, 'right': right})
    assert metrics.n_rows.eq(4).all() and metrics.n_censored.eq(2).all()
    assert metrics.macro_f1.eq(f1_score(left.y_true, left.y_pred, average='macro', labels=[0, 1], zero_division=0)).all()
    assert metrics.f1.eq(0).all()
    assert cm[['tn', 'fp', 'fn', 'tp']].values.tolist() == [[3, 0, 1, 0], [3, 0, 1, 0]]
    assert len(pairs) == 1 and pairs.iloc[0].max_score_difference == pytest.approx(0.05)
    assert len(left.columns) == len(predictions().columns)  # Inputs stay untouched.


@pytest.mark.parametrize('change,message', [
    (lambda x: x.iloc[:-1].copy(), 'cohort mismatch'),
    (lambda x: x.assign(y_true=[1, 0, 0, 1]), 'Label mismatch'),
    (lambda x: x.assign(prediction_time=x.prediction_time + pd.Timedelta(minutes=1)), 'Prediction-time mismatch'),
    (lambda x: pd.concat([x, x.iloc[:1]]), 'Duplicate event prediction'),
    (lambda x: x.assign(y_true=[0, 0, 0, pd.NA]), 'known binary'),
    (lambda x: x.assign(y_score=float('inf')), 'finite'),
    (lambda x: x.assign(prediction_time=x.prediction_time.dt.tz_localize(None)), 'timezone-aware'),
])
def test_invalid_or_unpaired_saved_runs_fail(change, message):
    with pytest.raises(ValueError, match=message):
        compare_saved_runs({'left': predictions(), 'right': change(predictions())})


def test_pairing_is_required_within_a_run_across_feature_sets():
    a = predictions()
    b = predictions().assign(feature_set='local+calendar', event_id=['other'] * 4)
    with pytest.raises(ValueError, match='Duplicate event prediction'):
        compare_saved_runs({'run': pd.concat([a, b], ignore_index=True)})
    b = predictions().assign(feature_set='local+calendar')
    b.loc[0, 'event_id'] = 'SYNTHETIC-DIFFERENT'
    with pytest.raises(ValueError, match='cohort mismatch'):
        compare_saved_runs({'run': pd.concat([a, b], ignore_index=True)})


def test_rule_scores_are_never_evaluated_as_probabilities():
    frame = predictions().assign(score_kind='rule_score', y_score=[-2, 0, 1, 3])
    metrics, _, _ = compare_saved_runs({'rule': frame})
    assert metrics.log_loss.isna().all() and metrics.brier_score.isna().all()


def test_an_event_cannot_leak_across_splits():
    frame = predictions()
    other = predictions().assign(split='validation')
    with pytest.raises(ValueError, match='changes prediction time or split'):
        compare_saved_runs({'run': pd.concat([frame, other], ignore_index=True)})
