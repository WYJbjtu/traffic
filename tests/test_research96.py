"""Offline identity, availability and missingness checks for research display adapters."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from traffic_recovery import research96 as r


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_spatial_metrics_have_exact_paired_event_hashes() -> None:
    frame = r.metrics(ROOT)
    for population in r.POPULATIONS:
        for model in ("random_forest", "xgboost"):
            for split in ("validation", "test"):
                base, spatial = r.paired_rows(frame, population, model, split, "M0", "M1")
                assert base.event_ids_sha256 == spatial.event_ids_sha256
                assert base.n_positive + base.n_negative == base.n_events
    p1 = r.paired_rows(frame, r.POPULATIONS[0], "random_forest", "test", "M0", "M1")[1]
    p2 = r.paired_rows(frame, r.POPULATIONS[1], "random_forest", "test", "M0", "M1")[1]
    assert p1.event_ids_sha256 != p2.event_ids_sha256
    assert p1.roc_auc == pytest.approx(0.7523, abs=0.00005)


def test_pairing_rejects_unmatched_ids_and_cross_population() -> None:
    frame = r.metrics(ROOT)
    changed = frame.copy()
    ix = changed.index[(changed.population == r.POPULATIONS[0]) & (changed.model == "random_forest")
                       & (changed.split == "test") & (changed.arm == "M1")][0]
    changed.loc[ix, "event_ids_sha256"] = "different"
    with pytest.raises(ValueError, match="different event IDs"):
        r.paired_rows(changed, r.POPULATIONS[0], "random_forest", "test", "M0", "M1")
    with pytest.raises(ValueError, match="cannot be paired"):
        r.paired_rows(frame, "INDEPENDENTLY_VERIFIED", "random_forest", "test", "M0", "M1")


def _frozen_file(root: Path, relative: str, frame: pd.DataFrame) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    digest = r.sha256(path)
    manifest = root / "reports/spatial96_inferred_v2/output_sha256.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({relative: digest}), encoding="utf-8")


def test_neighbor_lineage_rejects_future_availability(tmp_path: Path) -> None:
    prediction = pd.Timestamp("2026-01-01 10:00", tz=r.HKT)
    row = {"event_id": "real-id", "population": r.POPULATIONS[0],
           "observed_at": prediction - pd.Timedelta(minutes=15),
           "available_at": prediction + pd.Timedelta(minutes=1),
           "last_source_available_at": prediction - pd.Timedelta(minutes=5)}
    relative = "data/local/spatial96/inferred-v2/event_neighbor_lineage.parquet"
    _frozen_file(tmp_path, relative, pd.DataFrame([row]))
    event = pd.Series({"event_id": "real-id", "prediction_time": prediction})
    with pytest.raises(ValueError, match="Future neighbor observation"):
        r.event_lineage(tmp_path, event, r.POPULATIONS[0])


def test_bounded_bins_preserve_missing_speed_and_timezone(tmp_path: Path) -> None:
    start = pd.Timestamp("2026-01-01 09:50", tz=r.HKT)
    frame = pd.DataFrame({"detector_id": ["A", "A"], "direction": ["East", "East"],
                          "lane_id": ["Middle", "Middle"],
                          "timestamp": [start, start + pd.Timedelta(minutes=5)],
                          "speed_kmh": [25.0, float("nan")], "valid_slots": [2, 0],
                          "available_at": [start + pd.Timedelta(minutes=10)] * 2,
                          "last_source_available_at": [start] * 2, "usable": [True, False]})
    path = tmp_path / "data/local/expanded96-release/prepared-v1/processed/cohort_bins.parquet"
    path.parent.mkdir(parents=True)
    frame.to_parquet(path, index=False)
    manifest = tmp_path / "data/local/expanded96-release/model-a0-a2-v2/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"source_sha256": {"bins": r.sha256(path)}}), encoding="utf-8")
    result = r.observed_bins(tmp_path, "A", "East", "Middle", start, start + pd.Timedelta(minutes=10))
    assert len(result) == 2
    assert pd.isna(result.iloc[1].speed_kmh)
    assert str(result.timestamp.dt.tz) == r.HKT
    with pytest.raises(ValueError, match="bounded"):
        r.observed_bins(tmp_path, "A", "East", "Middle", start, start + pd.Timedelta(hours=9))


def test_missing_local_artifact_is_explicit(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="unavailable"):
        r.local_path(tmp_path, "data/local/missing.parquet")


def test_published_prediction_uses_event_id_and_checks_truth(tmp_path: Path) -> None:
    relative = "data/local/expanded96-release/model-a0-a2-v2/predictions.parquet"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    pd.DataFrame([
        {"event_id": "other", "split": "test", "horizon_min": 30, "feature_set": "A2_local_history",
         "model": "random_forest", "label": 0, "probability": .1, "prediction": 0},
        {"event_id": "selected", "split": "test", "horizon_min": 30, "feature_set": "A2_local_history",
         "model": "random_forest", "label": 1, "probability": .8, "prediction": 1},
    ]).to_parquet(path, index=False)
    (path.parent / "manifest.json").write_text(json.dumps({"target": "recovery_confirmation_v1",
        "outputs_sha256": {"predictions.parquet": r.sha256(path)}}), encoding="utf-8")
    event = pd.Series({"event_id": "selected", "split_proposal": "test", "label_30m": 1})
    result = r.published_local_scores(tmp_path, event, 30)
    assert len(result) == 1 and result.iloc[0].probability == .8
    event["label_30m"] = 0
    with pytest.raises(ValueError, match="target differs"):
        r.published_local_scores(tmp_path, event, 30)


def test_hk_grid_to_display_coordinates_are_transformed(tmp_path: Path) -> None:
    # Synthetic candidates exercise EPSG:2326 metres -> EPSG:4326 degrees.
    from pyproj import Transformer
    candidates = pd.DataFrame({"detector_id": ["D"] * 736,
        "direction": ["East"] * 736, "lane_id": ["Middle"] * 736,
        "arc_id": [str(i) for i in range(736)], "easting": [833758.0] * 736,
        "northing": [812147.0] * 736})
    _frozen_file(tmp_path, "data/local/spatial96/inferred-v2/mapping_scores.parquet", candidates)
    mapped = r.mappings(tmp_path)
    expected = Transformer.from_crs(2326, 4326, always_xy=True).transform(833758, 812147)
    assert (mapped.iloc[0].longitude, mapped.iloc[0].latitude) == pytest.approx(expected)
    assert 113 < mapped.iloc[0].longitude < 115
    assert 21 < mapped.iloc[0].latitude < 23


def test_unified_adapter_checks_hashes_and_paired_ids(tmp_path: Path) -> None:
    """Synthetic fixture, not empirical model evidence."""
    folder = tmp_path / "experiments/unified96/runs/p1-f0-f4-v1"
    folder.mkdir(parents=True)
    rows = pd.DataFrame([{"event_id": "e1", "split": "test", "model": "random_forest",
                          "feature_arm": arm, "y_true": 1, "y_score": score}
                         for arm, score in (("F0", .3), ("F4", .8))])
    rows.to_parquet(folder / "predictions.parquet", index=False)
    pd.DataFrame([{"model": "random_forest", "split": "test", "arm": arm, "n_events": 1}
                  for arm in ("F0", "F4")]).to_csv(folder / "metrics.csv", index=False)
    (folder / "paired_bootstrap.json").write_text("[]", encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({"target": "recovery_confirmation_v1",
        "population": "INFERRED_EXPLORATORY", "horizon_min": 30,
        "outputs_sha256": {name: r.sha256(folder / name) for name in
            ("predictions.parquet", "metrics.csv", "paired_bootstrap.json")}}), encoding="utf-8")
    scores, _, _ = r.unified_p1_run(tmp_path)
    assert scores.event_id.tolist() == ["e1", "e1"]
    rows.loc[1, "event_id"] = "unpaired"
    rows.to_parquet(folder / "predictions.parquet", index=False)
    with pytest.raises(ValueError, match="SHA-256"):
        r.unified_p1_run(tmp_path)
