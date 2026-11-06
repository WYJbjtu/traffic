"""Synthetic-only checks; these are not evidence of empirical spatial gain."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # historical scripts live outside installed package
from experiments.unified96.run import ARMS, event_hash, merge_verified, paired_bootstrap, require_available

HKT = "Asia/Hong_Kong"
T = pd.Timestamp("2025-05-01 12:00", tz=HKT)


def inputs():
    events = pd.DataFrame({"event_id": ["e1", "e2"], "detector_id": ["d1", "d2"],
        "direction": ["N", "S"], "lane_id": ["L", "L"], "prediction_time": [T, T],
        "split_proposal": ["train", "test"], "definition_version": ["lane-observed-confirmation-v1"] * 2,
        "label_30m": [1, 0], "reference_fit_end": [T - pd.Timedelta(days=1)] * 2,
        "feature_max_available_at": [T] * 2})
    history = pd.DataFrame({"event_id": ["e1", "e2"], "history_latest_available_at": [T - pd.Timedelta(minutes=5), pd.NaT]})
    spatial = pd.DataFrame({"event_id": ["e1", "e2"], "prediction_time": [T, T],
        "population": ["INFERRED_EXPLORATORY"] * 2, "observed_neighbor_count": [1, 0],
        "upstream_mean_speed_kmh": [25.0, float("nan")]})
    lineage = pd.DataFrame({"event_id": ["e1"], "population": ["INFERRED_EXPLORATORY"],
        "target_detector": ["d1"], "target_direction": ["N"], "target_lane": ["L"],
        "neighbor_detector": ["d2"], "neighbor_direction": ["S"], "neighbor_lane": ["L"],
        "side": ["upstream"], "observed_at": [T - pd.Timedelta(minutes=10)],
        "available_at": [T - pd.Timedelta(minutes=5)],
        "last_source_available_at": [T - pd.Timedelta(minutes=5)]})
    return events, history, spatial, lineage


def test_synthetic_identity_and_missing_speed():
    frame = merge_verified(*inputs(), "INFERRED_EXPLORATORY")
    assert frame.event_id.tolist() == ["e1"]
    assert pd.isna(inputs()[2].loc[1, "upstream_mean_speed_kmh"])
    assert "valid_slots" in ARMS["F0"] and "history_observed_bins" in ARMS["F0"]
    assert "upstream_mean_speed_kmh" in ARMS["F4"]


@pytest.mark.parametrize("which,change,pattern", [
    (0, lambda x: x.assign(event_id=["e1", "e1"]), "Duplicate"),
    (1, lambda x: x.assign(event_id=["e1", "missing"]), "History"),
    (2, lambda x: x.assign(prediction_time=[T + pd.Timedelta(minutes=5), T]), "join lost"),
    (3, lambda x: x.assign(available_at=[T + pd.Timedelta(minutes=1)]), "Future"),
    (3, lambda x: x.assign(target_detector=["wrong"]), "target unit"),
    (0, lambda x: x.assign(split_proposal=["train", "unknown"]), "split"),
    (0, lambda x: x.assign(feature_max_available_at=[pd.NaT, T]), "Missing"),
    (0, lambda x: x.assign(prediction_time=pd.to_datetime([T, T]).tz_localize(None)), "Timezone"),
])
def test_synthetic_fail_closed(which, change, pattern):
    frames = list(inputs()); frames[which] = change(frames[which])
    with pytest.raises(ValueError, match=pattern):
        merge_verified(*frames, "INFERRED_EXPLORATORY")


def test_synthetic_reject_p3_and_duplicate_hash():
    with pytest.raises(ValueError, match="P3"):
        merge_verified(*inputs(), "INDEPENDENTLY_VERIFIED")
    with pytest.raises(ValueError, match="duplicate"):
        event_hash(pd.Series(["a", "a"]))
    with pytest.raises(ValueError, match="Timezone"):
        require_available(pd.DataFrame({"prediction_time": [T], "available_at": [T.tz_localize(None)]}), "available_at")


def test_saved_real_run_event_pairing_and_metrics():
    """Verify saved authentic predictions; no new model is trained in this test."""
    import json
    from sklearn.metrics import roc_auc_score
    from traffic_recovery.data.http import sha256_file
    folder = Path(__file__).resolve().parents[1] / "experiments/unified96/runs/p1-f0-f4-v1"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["outputs_sha256"].items():
        assert sha256_file(folder / name) == expected
    scores = pd.read_parquet(folder / "predictions.parquet")
    metric = pd.read_csv(folder / "metrics.csv")
    assert not scores.duplicated(["event_id", "split", "model", "feature_arm"]).any()
    for row in metric.itertuples():
        subset = scores.loc[scores.model.eq(row.model) & scores.split.eq(row.split)
                            & scores.feature_arm.eq(row.arm)]
        assert len(subset) == row.n_events
        assert event_hash(subset.event_id) == row.event_ids_sha256
        assert roc_auc_score(subset.y_true, subset.y_score) == pytest.approx(row.roc_auc)


def test_synthetic_bootstrap_paired_detector_clusters():
    left = pd.DataFrame({"event_id": ["e1", "e2", "e3", "e4"],
        "detector_id": ["d1", "d1", "d2", "d2"], "y_true": [0, 1, 0, 1],
        "y_score": [.8, .2, .8, .2]})
    right = left.copy(); right["y_score"] = [0.1, 0.9, 0.2, 0.8]
    result = paired_bootstrap(left, right, replicates=25)
    assert result["clusters"] == 2 and result["events"] == 4
    assert result["roc_auc"]["valid_resamples"] == 25
    assert result["roc_auc"]["observed_delta"] == 1.0
    with pytest.raises(ValueError, match="Unpaired"):
        paired_bootstrap(left, right.assign(event_id=["other", "e2", "e3", "e4"]))
