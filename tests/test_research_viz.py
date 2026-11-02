"""Offline loader/filter tests; only labelled synthetic frames in unit fixtures."""
from pathlib import Path

import pandas as pd
import pytest

from traffic_recovery.research_viz import confusion_counts, event_history, join_event_metadata, load_artifacts, select_predictions, temporal_summary

ROOT = Path(__file__).resolve().parents[1]


def test_saved_runs_are_distinct_and_test_only():
    member, mp, meta = load_artifacts(ROOT, "member4")
    tianhao, tp, _ = load_artifacts(ROOT, "tianhao")
    assert set(member.horizon_min) == {15, 30, 60}
    assert set(tianhao.horizon_min) == {30}
    assert set(mp.split) == set(tp.split) == {"test"}
    assert "calendar" not in " ".join(member.feature_set.unique())
    assert "calendar" in " ".join(tianhao.feature_set.unique())
    assert meta.events.iloc[0] == 7597
    arm = select_predictions(mp, model="random_forest", feature_set="local+history+flow", horizon=30)
    assert len(arm) == 1363
    assert sum(map(sum, confusion_counts(arm))) == 1363


def test_reject_unlisted_run():
    with pytest.raises(ValueError, match="Unknown experiment"):
        load_artifacts(ROOT, "combined")


def test_synthetic_history_excludes_future_and_wrong_lane(tmp_path):
    when = pd.Timestamp("2026-01-02 12:00", tz="Asia/Hong_Kong")
    pd.DataFrame({"detector_id": ["01", "01", "01", "02"], "direction": ["N"]*4,
                  "lane_id": ["Fast", "Fast", "Slow", "Fast"],
                  "timestamp": [when-pd.Timedelta(minutes=15), when-pd.Timedelta(minutes=5), when, when],
                  "available_at": [when-pd.Timedelta(minutes=5), when+pd.Timedelta(minutes=5), when, when],
                  "speed_kmh": [12, 99, 7, 8]}).to_parquet(tmp_path / "bins.parquet")
    event = pd.Series({"detector_id": "01", "direction": "N", "lane_id": "Fast", "prediction_time": when})
    result = event_history(tmp_path / "bins.parquet", event)
    assert result.speed_kmh.tolist() == [12]


def test_synthetic_join_rejects_wrong_cohort_and_checks_time():
    instant = pd.Timestamp("2026-01-02 12:00", tz="Asia/Hong_Kong")
    predictions = pd.DataFrame({"event_id": ["a"], "prediction_time": [instant]})
    events = pd.DataFrame({"event_id": ["a"], "prediction_time": [instant], "detector_id": ["01"],
                           "direction": ["N"], "lane_id": ["Fast"]})
    assert join_event_metadata(predictions, events).detector_id.iloc[0] == "01"
    with pytest.raises(ValueError, match="no matching event/time"):
        join_event_metadata(predictions, events.assign(prediction_time=instant + pd.Timedelta(minutes=5)))


def test_synthetic_temporal_keeps_unknown_and_requires_unique_events():
    frame = pd.DataFrame({"event_id": ["a", "b"], "prediction_time": [pd.Timestamp("2026-01-05 08:00", tz="Asia/Hong_Kong")]*2,
                          "label_30m": pd.Series([1, pd.NA], dtype="Int8")})
    result = temporal_summary(frame)
    assert result.events.sum() == 2
    assert result.known.sum() == 1
    assert result.recovered.sum() == 1
    assert result.missing_rate.iloc[0] == .5
    with pytest.raises(ValueError, match="unique"):
        temporal_summary(frame.assign(event_id="same"))
