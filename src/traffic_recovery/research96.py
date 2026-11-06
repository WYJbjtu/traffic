"""Read-only adapters for the frozen 96-lane research explorer.

All road distances are EPSG:2326 metres, displayed coordinates are EPSG:4326,
speeds are km/h, and timestamps are aware Asia/Hong_Kong. Missing local evidence
raises FileNotFoundError; mismatched identity or provenance raises ValueError.
"""
from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache

import pandas as pd
import pyarrow.dataset as ds
from pyproj import Transformer
from shapely import wkb

from traffic_recovery.data.http import sha256_file as sha256

HKT = "Asia/Hong_Kong"
POPULATIONS = ("INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED")
UNIT = ("detector_id", "direction", "lane_id")


def verified_file(root: Path, relative: str) -> Path:
    """Find a published inferred-v2 file and check its frozen output digest."""
    hashes = json.loads((root / "reports/spatial96_inferred_v2/output_sha256.json").read_text(encoding="utf-8"))
    if relative not in hashes:
        raise ValueError(f"No frozen inferred-v2 SHA-256 for {relative}")
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Local research artifact unavailable: {path}")
    if sha256(path) != hashes[relative]:
        raise ValueError(f"Frozen research artifact changed: {path}")
    return path


def metrics(root: Path, *, controls: bool = False) -> pd.DataFrame:
    """Load saved aggregate metrics; no scores or curves are synthesized."""
    name = "spatial_negative_controls.csv" if controls else "paired_spatial_metrics.csv"
    frame = pd.read_csv(verified_file(root, f"reports/spatial96_inferred_v2/{name}"), dtype={"event_ids_sha256": str})
    if frame.duplicated(["population", "arm", "model", "split"]).any():
        raise ValueError("Duplicate spatial metrics identity")
    manifest = json.loads((root / "data/local/expanded96-release/model-a0-a2-v2/manifest.json").read_text(encoding="utf-8")) if (root / "data/local/expanded96-release/model-a0-a2-v2/manifest.json").is_file() else None
    if manifest is not None and manifest["target"] != "recovery_confirmation_v1":
        raise ValueError("Local Release target differs from inferred-v2 report")
    # The target/version is published in the frozen Release manifest; aggregate
    # PR #21 rows themselves record only the event hash and 30-minute task.
    frame["target_version"] = manifest["target"] if manifest is not None else "recovery_confirmation_v1"
    frame["horizon_min"] = 30
    frame["source_provenance"] = f"reports/spatial96_inferred_v2/{name}"
    return frame


def paired_rows(frame: pd.DataFrame, population: str, model: str, split: str,
                left: str, right: str) -> tuple[pd.Series, pd.Series]:
    """Return two arms only when target cohort, event hash and supports agree."""
    if population not in POPULATIONS:
        raise ValueError("P1/P2 populations cannot be paired across cohorts")
    rows = []
    for arm in (left, right):
        hit = frame.loc[frame.population.eq(population) & frame.model.eq(model)
                        & frame.split.eq(split) & frame.arm.eq(arm)]
        if len(hit) != 1:
            raise ValueError(f"Missing or duplicate paired row: {population}/{arm}/{model}/{split}")
        rows.append(hit.iloc[0])
    a, b = rows
    if (a.target_version != b.target_version or int(a.horizon_min) != int(b.horizon_min)
        or not a.event_ids_sha256 or a.event_ids_sha256 != b.event_ids_sha256 or any(
        int(a[col]) != int(b[col]) for col in ("n_events", "n_positive", "n_negative")
    )):
        raise ValueError("Spatial arms have different event IDs or target supports")
    return a, b


def local_path(root: Path, relative: str, expected_sha: str | None = None) -> Path:
    """Resolve an explicit local artifact; optionally verify immutable source bytes."""
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Local authenticated data unavailable: {path}")
    if expected_sha is not None and sha256(path) != expected_sha:
        raise ValueError(f"Authenticated local data SHA-256 mismatch: {path}")
    return path


def release_events(root: Path) -> pd.DataFrame:
    """Load the 30,452 authentic events after checking the frozen source hash."""
    manifest = json.loads((root / "data/local/expanded96-release/model-a0-a2-v2/manifest.json").read_text(encoding="utf-8"))
    path = local_path(root, "data/local/expanded96-release/prepared-v1/processed/events.parquet",
                      manifest["source_sha256"]["events"])
    frame = pd.read_parquet(path)
    if len(frame) != 30452 or frame.event_id.duplicated().any() or frame[list(UNIT)].drop_duplicates().shape[0] != 94:
        raise ValueError("Expanded96 event cohort differs from frozen release")
    if manifest["target"] != "recovery_confirmation_v1" or not set(frame.definition_version) == {"lane-observed-confirmation-v1"}:
        raise ValueError("Unexpected recovery target version")
    return frame


def mappings(root: Path) -> pd.DataFrame:
    """Return all 736 scored candidates, including incompatible alternatives."""
    frame = pd.read_parquet(verified_file(root, "data/local/spatial96/inferred-v2/mapping_scores.parquet"))
    if len(frame) != 736 or frame.duplicated([*UNIT, "arc_id"]).any():
        raise ValueError("Unexpected mapping inventory")
    transformer = Transformer.from_crs(2326, 4326, always_xy=True)
    longitude, latitude = transformer.transform(frame.easting.to_numpy(), frame.northing.to_numpy())
    return frame.assign(longitude=longitude, latitude=latitude)


def neighbors(root: Path, population: str = "INFERRED_EXPLORATORY") -> pd.DataFrame:
    """Load selected source supported inferred paths, never approved routing."""
    if population not in POPULATIONS:
        raise ValueError("No independently verified path population exists")
    frame = pd.read_parquet(verified_file(root, "data/local/spatial96/inferred-v2/inferred_detector_neighbors.parquet"))
    return frame.loc[frame.population.eq(population) & frame.selected_path].copy()


def event_lineage(root: Path, event: pd.Series, population: str) -> pd.DataFrame:
    """Return saved neighbor observations whose end and availability precede prediction."""
    if population not in POPULATIONS:
        raise ValueError("Unknown inferred population")
    path = verified_file(root, "data/local/spatial96/inferred-v2/event_neighbor_lineage.parquet")
    frame = ds.dataset(path).to_table(filter=(ds.field("event_id") == str(event.event_id))
                                      & (ds.field("population") == population)).to_pandas()
    cutoff = pd.Timestamp(event.prediction_time)
    for col in ("observed_at", "available_at", "last_source_available_at"):
        if frame[col].notna().any() and (pd.to_datetime(frame[col], utc=True) > cutoff).any():
            raise ValueError(f"Future neighbor observation leaked through {col}")
    return frame


def event_features(root: Path, event: pd.Series, population: str) -> pd.Series:
    """Read genuine saved S1–S4 features for one event and population."""
    path = verified_file(root, "data/local/spatial96/inferred-v2/event_spatial_features.parquet")
    frame = ds.dataset(path).to_table(filter=(ds.field("event_id") == str(event.event_id))
                                      & (ds.field("population") == population)).to_pandas()
    if len(frame) != 1 or pd.Timestamp(frame.iloc[0].prediction_time) != pd.Timestamp(event.prediction_time):
        raise ValueError("Spatial features do not match the selected event/time")
    return frame.iloc[0]


def unified_p1_run(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Read authenticated exploratory P1 F0/F4 scores, metrics and cluster intervals.

    Rejects changed files, duplicate event-arm identity and inconsistent paired IDs.
    Does not substitute these refitted P1 scores for the frozen PR #21 M0/M1 run.
    """
    folder = root / "experiments/unified96/runs/p1-f0-f4-v1"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["target"] != "recovery_confirmation_v1" or
        manifest["population"] != "INFERRED_EXPLORATORY" or manifest["horizon_min"] != 30):
        raise ValueError("Unexpected unified experiment identity")
    for name, digest in manifest["outputs_sha256"].items():
        local_path(root, str(folder.relative_to(root) / name), digest)
    scores = pd.read_parquet(folder / "predictions.parquet")
    metrics = pd.read_csv(folder / "metrics.csv")
    bootstrap = json.loads((folder / "paired_bootstrap.json").read_text(encoding="utf-8"))
    identity = ["event_id", "split", "model", "feature_arm"]
    if scores.duplicated(identity).any() or not set(scores.feature_arm) == {"F0", "F4"}:
        raise ValueError("Duplicate or missing unified prediction identity")
    for (model, split), group in scores.groupby(["model", "split"]):
        a = group.loc[group.feature_arm.eq("F0")]
        b = group.loc[group.feature_arm.eq("F4")]
        if (len(a) != len(b) or not a.event_id.is_unique or not b.event_id.is_unique or
            set(a.event_id) != set(b.event_id)):
            raise ValueError(f"Unpaired unified event IDs: {model}/{split}")
        recorded = metrics.loc[metrics.model.eq(model) & metrics.split.eq(split)]
        if len(recorded) != 2 or any(int(row.n_events) != len(a) for row in recorded.itertuples()):
            raise ValueError(f"Unified metric support mismatch: {model}/{split}")
    return scores, metrics, bootstrap


def published_local_scores(root: Path, event: pd.Series, horizon: int) -> pd.DataFrame:
    """Read saved full-cohort local/history scores by exact event identity.

    These scores belong to the separate A0–A2 v2 experiment, not PR #21's
    restricted-population M0 refit, so callers must never label them paired M0.
    Unknown/censored labels yield an empty frame.
    """
    if horizon not in (15, 30, 60):
        raise ValueError("Unsupported published horizon")
    manifest = json.loads((root / "data/local/expanded96-release/model-a0-a2-v2/manifest.json").read_text(encoding="utf-8"))
    if manifest["target"] != "recovery_confirmation_v1":
        raise ValueError("Published local target differs")
    path = local_path(root, "data/local/expanded96-release/model-a0-a2-v2/predictions.parquet",
                      manifest["outputs_sha256"]["predictions.parquet"])
    frame = ds.dataset(path).to_table(
        filter=(ds.field("event_id") == str(event.event_id))
               & (ds.field("split") == str(event.split_proposal))
               & (ds.field("horizon_min") == horizon)
               & (ds.field("feature_set") == "A2_local_history"),
        columns=["event_id", "split", "horizon_min", "feature_set", "model", "label", "probability", "prediction"]
    ).to_pandas()
    frame = frame.loc[frame.model.isin(["random_forest", "xgboost"])].copy()
    if frame.empty:
        return frame
    if frame.duplicated(["event_id", "split", "horizon_min", "feature_set", "model"]).any():
        raise ValueError("Duplicate published local prediction identity")
    label = event[f"label_{horizon}m"]
    if pd.isna(label) or not frame.label.eq(int(label)).all():
        raise ValueError("Published local prediction target differs from frozen event")
    frame["target_version"] = manifest["target"]
    frame["source_provenance"] = "data/local/expanded96-release/model-a0-a2-v2/predictions.parquet"
    return frame


def observed_bins(root: Path, detector: str, direction: str, lane: str,
                  start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Query only one lane and bounded HKT window from the 35.8m-row Parquet.

    Future rows remain in this retrospective display only. The function does not
    turn them into model features; missing timestamps are returned as missing.
    """
    if start.tzinfo is None or end.tzinfo is None or end <= start or end-start > pd.Timedelta(hours=8):
        raise ValueError("A bounded, timezone-aware observation window is required")
    manifest = json.loads((root / "data/local/expanded96-release/model-a0-a2-v2/manifest.json").read_text(encoding="utf-8"))
    path = local_path(root, "data/local/expanded96-release/prepared-v1/processed/cohort_bins.parquet")
    _verify_large(path, manifest["source_sha256"]["bins"])
    columns = ["detector_id", "direction", "lane_id", "timestamp", "speed_kmh", "valid_slots",
               "available_at", "last_source_available_at", "usable"]
    predicate = ((ds.field("detector_id") == detector) & (ds.field("direction") == direction)
                 & (ds.field("lane_id") == lane) & (ds.field("timestamp") >= start.to_pydatetime())
                 & (ds.field("timestamp") <= end.to_pydatetime()))
    frame = ds.dataset(path).to_table(columns=columns, filter=predicate).to_pandas()
    if frame.duplicated([*UNIT, "timestamp"]).any():
        raise ValueError("Duplicate five-minute observation key")
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True).dt.tz_convert(HKT)
    return frame.sort_values("timestamp")


@lru_cache(maxsize=2)
def _verify_large(path: Path, expected: str) -> None:
    if sha256(path) != expected:
        raise ValueError(f"Authenticated local data SHA-256 mismatch: {path}")


def route_paths(root: Path, route_ids: set[str]) -> dict[str, list[list[float]]]:
    """Read only geometry tiles containing selected source route IDs."""
    if not route_ids:
        return {}
    import sqlite3
    network = root / "data/local/network-full/v1"
    if not (network / "topology_index.sqlite").is_file():
        raise FileNotFoundError("Official road SQLite index unavailable")
    with sqlite3.connect(f"file:{network / 'topology_index.sqlite'}?mode=ro", uri=True) as db:
        placeholders = ",".join("?" for _ in route_ids)
        tiles = {r[0] for r in db.execute(
            f"SELECT DISTINCT tile FROM arcs WHERE route IN ({placeholders})", tuple(route_ids))}
    paths: dict[str, list[list[float]]] = {}
    for tile in tiles:
        folder = network / "geometry" / f"tile={tile}"
        table = ds.dataset(folder, format="parquet").to_table(
            columns=["route_id", "geometry_wkb_4326"], filter=ds.field("route_id").isin(list(route_ids)))
        for row in table.to_pylist():
            paths[str(row["route_id"])] = [list(point) for point in wkb.loads(row["geometry_wkb_4326"]).coords]
    if route_ids - paths.keys():
        raise ValueError(f"Missing official geometry for routes: {sorted(route_ids-paths.keys())}")
    return paths
