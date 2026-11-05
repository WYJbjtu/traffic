"""Synthetic offline checks; these rows are not research observations."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ensemble_external96", ROOT / "experiments/member4/ensemble_external96.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_frames(monkeypatch):
    monkeypatch.setattr(module, "EXPECTED_EVENT_COUNT", 3)
    monkeypatch.setattr(module, "EXPECTED_SPLITS", {"train": 1, "validation": 1, "test": 1})
    contract = module.ExperimentContract.from_path(module.CONTRACT)
    dates = pd.to_datetime(["2024-05-01T12:00:00+08:00", "2025-05-01T12:00:00+08:00",
                            "2026-05-01T12:00:00+08:00"], utc=True).tz_convert("Asia/Hong_Kong")
    events = pd.DataFrame({"event_id": ["one", "two", "three"], "prediction_time": dates,
        "detector_id": ["d1", "d2", "d3"], "direction": ["E", "E", "W"],
        "lane_id": ["L", "L", "L"], "label_30m": pd.Series([1, 0, 1], dtype="Int8"),
        "split_proposal": ["train", "validation", "test"],
        "definition_version": ["lane-observed-confirmation-v1"] * 3})
    features = events.rename(columns={"split_proposal": "split"}).drop(columns="definition_version").copy()
    return features, events, contract


def test_exact_alignment_and_shuffled_release(monkeypatch):
    features, events, contract = fixture_frames(monkeypatch)
    aligned = module.aligned_features(features, events.iloc[::-1].reset_index(drop=True), contract)
    assert aligned.event_id.tolist() == ["one", "two", "three"]
    for field, value in (("label_30m", 0), ("prediction_time", pd.Timestamp("2024-05-02", tz="Asia/Hong_Kong")),
                         ("detector_id", "wrong"), ("split", "test")):
        tampered = features.copy()
        tampered.loc[0, field] = value
        with pytest.raises(ValueError):
            module.aligned_features(tampered, events, contract)


def test_missing_or_wrong_target_rejected(monkeypatch):
    features, events, contract = fixture_frames(monkeypatch)
    with pytest.raises(ValueError, match="identity mismatch"):
        module.aligned_features(features, events.iloc[:-1], contract)
    events.loc[0, "definition_version"] = "recovery_start_v1"
    with pytest.raises(ValueError, match="definition"):
        module.aligned_features(features, events, contract)


def test_existing_output_never_overwritten(tmp_path):
    output = tmp_path / "results"
    output.mkdir()
    with pytest.raises(FileExistsError):
        module.run(release_dir=tmp_path, source_cache=tmp_path,
                   prepared_dir=tmp_path, output=output)
