"""Negative controls for inferred-v2: geographic, undirected, time/region shuffle.

Controls share P1 event IDs and train-only fits. Geographic distance is NOT
network distance; its feature extraction uses speed/ratio only, and its lineage
explicitly labels straight-line distance as such. No model output tunes topology.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import zipfile
import io

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from traffic_recovery.data.http import sha256_file
from traffic_recovery.network.inferred_v2 import spatial_features, SIDES
from traffic_recovery.network.spatial96 import verify_release
from spatial96_inferred_v2 import evaluate, S1, LOCAL, HISTORY

LOCAL_DATA = Path("data/local/spatial96/inferred-v2")
REPORT = Path("reports/spatial96_inferred_v2")


def undirected(features: pd.DataFrame) -> pd.DataFrame:
    """Pool available observations, remove upstream/downstream distinction."""
    f = features.copy()
    upstream_n = f.upstream_observed_count.copy()
    downstream_n = f.downstream_observed_count.copy()
    n = upstream_n + downstream_n
    for field in ("mean_speed_kmh", "mean_ratio", "mean_age_minutes", "coverage"):
        a = f[f"upstream_{field}"]; b = f[f"downstream_{field}"]
        if field == "coverage":
            combined = pd.concat([a, b], axis=1).mean(axis=1)
        else:
            combined = (a.fillna(0) * upstream_n + b.fillna(0) * downstream_n) / n.replace(0, np.nan)
        for side in SIDES:
            f[f"{side}_{field}"] = combined
            f[f"{side}_observed_count"] = n
            f[f"{side}_missing"] = (n == 0).astype(int)
    return f


def shuffle_contemporaneous(features: pd.DataFrame, events: pd.DataFrame,
                            locations: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Permute S1 between different detectors within exact HKT prediction time
    and 5km source grid cells; no future information, fixed seed 42. Singletons
    stay unchanged and are reported rather than shuffled across time/region.
    """
    f = features.copy()
    loc = locations.drop_duplicates("detector_id")[["detector_id", "easting", "northing"]]
    strat = events[["event_id", "detector_id", "prediction_time"]].merge(loc, on="detector_id", validate="many_to_one")
    strat = f[["event_id"]].merge(strat, on="event_id", validate="one_to_one")
    strat["grid_x"] = np.floor(strat.easting / 5000)
    strat["grid_y"] = np.floor(strat.northing / 5000)
    rng = np.random.default_rng(42)
    swaps = 0
    index = {event_id: i for i, event_id in enumerate(f.event_id)}
    original = f[S1].copy()
    for _, group in strat.groupby(["prediction_time", "grid_x", "grid_y"], dropna=False):
        # Only disjoint target detectors; avoid self-identity and source reuse.
        group = group.drop_duplicates("detector_id")
        if len(group) < 2:
            continue
        indices = [index[e] for e in group.event_id]
        shift = int(rng.integers(1, len(indices)))
        donors = np.roll(indices, shift)
        f.loc[indices, S1] = original.iloc[donors][S1].to_numpy()
        swaps += len(indices)
    return f, swaps


def geographic_paths(locations: pd.DataFrame) -> pd.DataFrame:
    """Nearest detector within fixed 250m EPSG:2326 radius, no road semantics."""
    loc = locations.drop_duplicates("detector_id")
    pair = {}
    for a in loc.itertuples(index=False):
        near = sorted(((np.hypot(a.easting-b.easting, a.northing-b.northing), b)
                       for b in loc.itertuples(index=False) if b.detector_id != a.detector_id), key=lambda x: x[0])
        if not near or near[0][0] > 250:
            continue
        distance, b = near[0]
        first, second = sorted([a, b], key=lambda r:r.detector_id)
        pair[(first.detector_id, second.detector_id)] = dict(
            upstream_detector=first.detector_id, upstream_direction=first.direction, upstream_lane=first.lane_id,
            downstream_detector=second.detector_id, downstream_direction=second.direction, downstream_lane=second.lane_id,
            arc_sequence="GEOGRAPHIC_ONLY", route_sequence="GEOGRAPHIC_ONLY", arc_count=1,
            path_distance_m=float(distance), alternative_paths=1, selected_path=True,
            upstream_tier="GEOGRAPHIC_ONLY", downstream_tier="GEOGRAPHIC_ONLY", population="GEOGRAPHIC_ONLY")
    return pd.DataFrame(pair.values())


def run() -> None:
    archive = Path("data/local/expanded96-release/HK_Traffic_Expanded_96_Prepared_Data_v1.zip")
    release = Path("data/local/expanded96-release/prepared-v1")
    _, events, manifest = verify_release(archive, release)
    history = Path("data/local/expanded96-release/model-a0-a2-v2/history_features.parquet")
    if sha256_file(history) != json.loads((history.parent / "manifest.json").read_text())["outputs_sha256"][history.name]:
        raise ValueError("History hash mismatch")
    events = events.merge(pd.read_parquet(history), on="event_id", validate="one_to_one")
    f = pd.read_parquet(LOCAL_DATA / "event_spatial_features.parquet")
    base = f.loc[f.population.eq("INFERRED_EXPLORATORY")].reset_index(drop=True)
    ids = set(base.loc[base.observed_neighbor_count.gt(0), "event_id"])
    if not ids:
        raise ValueError("P1 has no observed neighbors")
    loc = pd.read_csv("reports/spatial96_nov05/mapping_summary.csv")
    with zipfile.ZipFile(archive) as z:
        refs = pd.read_parquet(io.BytesIO(z.read("reports/full_january_reference.parquet")))
    geo_paths = geographic_paths(loc)
    if geo_paths.empty:
        raise ValueError("No geographic control neighbors")
    geo_detail, geo = spatial_features(events, geo_paths, release / "processed/cohort_bins.parquet", refs,
                    bins_sha256=manifest["files"]["processed/cohort_bins.parquet"]["sha256"])
    # Feature extractor uses generic distance field internally; re-label the
    # control lineage explicitly: these are straight-line distances, NOT paths.
    geo_detail = geo_detail.rename(columns={"network_distance_m": "straight_line_distance_m"})
    geo_detail.to_parquet(LOCAL_DATA / "geographic_control_lineage.parquet", index=False)
    geo = undirected(geo)
    geo.to_parquet(LOCAL_DATA / "geographic_control_features.parquet", index=False)
    shuffle, swaps = shuffle_contemporaneous(base, events, loc)
    controls = {"C1_geographic": geo, "C2_undirected": undirected(base),
                "C4_time_region_shuffle": shuffle}
    arms = {"M0": LOCAL + HISTORY, "M1": LOCAL + HISTORY + S1}
    outputs = []
    for name, features in controls.items():
        m, _ = evaluate(events, features, name, arms=arms, eligible_ids=ids)
        m["shuffle_swapped_events"] = swaps if name.startswith("C4") else 0
        m["geographic_observed_events"] = int(geo.observed_neighbor_count.gt(0).sum()) if name.startswith("C1") else np.nan
        outputs.append(m)
    published = pd.read_csv(REPORT / "paired_spatial_metrics.csv")
    outputs.append(published.loc[published.arm.isin(["M0", "M1"]) & published.population.isin(
        ["INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED"])].assign(
        population=lambda d:d.population.map({"INFERRED_EXPLORATORY": "C3_directed",
                                               "HIGH_CONFIDENCE_INFERRED": "C5_high_confidence"})))
    pd.concat(outputs, ignore_index=True).to_csv(REPORT / "spatial_negative_controls.csv", index=False)
    sensitivity = pd.DataFrame([{"population": pop,
        "max_network_distance_m": limit, "pairs": int(paths.loc[paths.selected_path & paths.path_distance_m.le(limit)].shape[0]),
        "meaning": "coverage-only; no test-score-based selection"}
        for pop in ("INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED")
        for paths in [pd.read_parquet(LOCAL_DATA / f"paths_{pop}.parquet")]
        for limit in (250, 500, 1000)])
    sensitivity.to_csv(REPORT / "network_sensitivity.csv", index=False)
    source = json.loads((REPORT / "source_sha256.json").read_text())
    source[str(history)] = sha256_file(history)
    (REPORT / "source_sha256.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    outputs = {str(p.resolve().relative_to(ROOT)): sha256_file(p) for folder in (LOCAL_DATA, REPORT)
               for p in folder.iterdir() if p.is_file() and p.name != "output_sha256.json"}
    (REPORT / "output_sha256.json").write_text(json.dumps(outputs, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    run()
