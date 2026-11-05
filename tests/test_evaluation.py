"""SYNTHETIC metric regressions; no observations or empirical model claims."""
import pandas as pd
import pytest
from sklearn.metrics import f1_score

from traffic_recovery.models.evaluation import evaluate_predictions


@pytest.mark.parametrize("truth,predicted", [
    ([0, 0, 0, 1], [0, 0, 0, 0]),
    ([0, 1, 0, 1], [0, 1, 1, 0]),
    ([0, 0], [0, 0]),
])
def test_macro_f1_is_distinct_from_positive_class_f1(truth, predicted) -> None:
    size = len(truth)
    frame = pd.DataFrame({
        "version": "SYNTHETIC", "event_id": [f"synthetic-{i}" for i in range(size)],
        "split": "test", "horizon_min": 30, "model": "synthetic",
        "feature_set": "local", "y_true": truth, "y_pred": predicted,
        "y_score": predicted, "score_kind": "probability",
        "n_censored_in_split": 0, "n_missing_feature_in_split": 0,
    })
    metrics = evaluate_predictions(frame, version_column="version").set_index("metric_name")
    expected = f1_score(truth, predicted, average="macro", labels=[0, 1], zero_division=0)
    assert "macro_f1" in metrics.index
    assert metrics.loc["macro_f1", "metric_value"] == pytest.approx(expected)
