"""Retrospective inferred-network experiment; NOT verified legal/historical routing.

Fixed geometric/metadata quality policy, declared before model evaluation. All
coordinates and network distances are EPSG:2326 metres. A missing TURN record
never certifies legality. No label or model score enters ranking or path selection.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from traffic_recovery.network.spatial96 import UNIT

KEY = UNIT
MAX_AGE_NS = int(pd.Timedelta(minutes=10).value)
SIDES = ("upstream", "downstream")


def score_mappings(candidates: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    """Rank ALL candidates. High: <=25m, <=30 degrees, name, grade 0,
    matching detector metadata and >=0.2 score margin to the next compatible arc.
    Grade 0 describes road only: unknown detector height remains a caveat.
    Scores are unitless, not calibrated match probabilities.
    """
    if candidates.duplicated(KEY + ["arc_id"]).any() or inventory.duplicated(KEY).any():
        raise ValueError("Duplicate mapping identity")
    c = candidates.copy()
    c["score"] = (c.distance_m / 50 + c.directional_error_deg / 45
                  + c.name_evidence.ne("name_in_detector_description").astype(float) * .5
                  + c.elevation.ne("0").astype(float) * .5
                  + (~c.metadata_direction_agrees).astype(float) * .5)
    c.loc[~c.direction_compatible, "score"] = np.inf
    c = c.sort_values(KEY + ["score", "distance_m", "arc_id"]).reset_index(drop=True)
    c["rank"] = c.groupby(KEY).cumcount() + 1
    margins = {}
    for key, group in c.groupby(KEY):
        good = group.loc[group.direction_compatible]
        margins[key] = (float(good.score.iloc[1] - good.score.iloc[0]) if len(good) > 1
                        else np.inf)
    c["score_margin"] = [margins[tuple(row)] for row in c[KEY].itertuples(index=False, name=None)]
    high = (c.direction_compatible & c["rank"].eq(1) & c.distance_m.le(25)
            & c.directional_error_deg.le(30) & c.name_evidence.eq("name_in_detector_description")
            & c.elevation.eq("0") & c.metadata_direction_agrees & c.score_margin.ge(.2))
    c["quality_tier"] = np.select([high, c.direction_compatible],
        ["HIGH_CONFIDENCE_INFERRED", "AMBIGUOUS_INFERRED"], default="DIRECTION_INCOMPATIBLE")
    # Inventory includes units without a 50m candidate: explicit unmatched records.
    missing = inventory.merge(c[KEY].drop_duplicates(), on=KEY, how="left", indicator=True)
    for row in missing.loc[missing._merge.eq("left_only"), KEY].itertuples(index=False, name=None):
        c = pd.concat([c, pd.DataFrame([{**dict(zip(KEY, row)), "quality_tier": "UNMATCHED",
            "score": np.nan, "score_margin": np.nan, "rank": 0}])], ignore_index=True)
    return c


def inferred_paths(paths: pd.DataFrame, mappings: pd.DataFrame, population: str) -> pd.DataFrame:
    """Select one canonical path per directed detector pair, retaining alternatives.

    Endpoint paths come from source-elevation-aware SQLite graph. Require source
    INTERSECTION membership for every cross-route transition, not mere crossing;
    source TURN-prohibited movements already removed by the v1 path enumerator.
    This is still *not* proof that other movements are legally permitted.
    """
    if population not in ("INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED"):
        raise ValueError("Unknown inferred population")
    best = mappings.loc[mappings["rank"].eq(1) & mappings.quality_tier.isin(
        ["HIGH_CONFIDENCE_INFERRED", "AMBIGUOUS_INFERRED"])].set_index(KEY)
    rows = []
    for row in paths.itertuples(index=False):
        a = (row.upstream_detector, row.upstream_direction, row.upstream_lane)
        b = (row.downstream_detector, row.downstream_direction, row.downstream_lane)
        if a not in best.index or b not in best.index or a[0] == b[0]:
            continue
        ma, mb = best.loc[a], best.loc[b]
        if row.from_arc != ma.arc_id or row.to_arc != mb.arc_id:
            continue  # alternative mapping paths remain in raw mapping/path evidence
        if population == "HIGH_CONFIDENCE_INFERRED" and (
            ma.quality_tier != population or mb.quality_tier != population):
            continue
        routes = row.route_sequence.split("|")
        # One intersection identifier per change of route; unsourced joins excluded.
        if len([i for i in row.intersection_ids.split("|") if i]) < sum(
            x != y for x, y in zip(routes, routes[1:])):
            continue
        if row.path_distance_m <= 0 or row.path_distance_m > 1000:
            continue
        rows.append({**row._asdict(), "population": population,
            "upstream_tier": ma.quality_tier, "downstream_tier": mb.quality_tier,
            "upstream_offset_m": float(ma.distance_m), "downstream_offset_m": float(mb.distance_m)})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    pair = ["upstream_detector", "downstream_detector"]
    result = result.sort_values(["path_distance_m", "arc_count", "arc_sequence"])
    result["alternative_paths"] = result.groupby(pair).path_distance_m.transform("size")
    result["selected_path"] = ~result.duplicated(pair)
    return result.reset_index(drop=True)


def inferred_transitions(db: sqlite3.Connection) -> pd.DataFrame:
    """Construct separate intersection-supported directed endpoint graph.

    Match exact centimetre endpoint AND source elevation node; cross-route
    movements need shared official INTERSECTION membership; block any recorded
    TURN restriction, regardless of conditional detail. A non-prohibited turn
    is still *unknown legality*. Interior crossings are never joined blindly.
    """
    arcs = db.execute("SELECT arc, route, from_node, to_node, length_m FROM arcs").fetchall()
    outgoing = defaultdict(list)
    for arc in arcs:
        outgoing[arc[2]].append(arc)
    memberships = defaultdict(set)
    for route, node, intersection in db.execute("SELECT route, node, int_id FROM intersection_routes"):
        memberships[(route, node)].add(intersection)
    banned = defaultdict(set)
    for source, target, turn_id in db.execute("SELECT from_route, to_route, turn_id FROM restrictions"):
        banned[(source, target)].add(turn_id)
    rows = []
    for arc, route, start, end, length in arcs:
        for next_arc, next_route, next_start, next_end, next_length in outgoing[end]:
            if route == next_route or banned[(route, next_route)]:
                continue
            shared = memberships[(route, end)] & memberships[(next_route, end)]
            if not shared:
                continue
            rows.append({"from_arc": arc, "to_arc": next_arc, "endpoint_node": end,
                "intersection_ids": "|".join(sorted(shared)), "from_route": route, "to_route": next_route,
                "from_length_m": length, "to_length_m": next_length,
                "grade_node": end.rsplit(":", 1)[-1], "connectivity": "SOURCE_INTERSECTION_ENDPOINT_INFERRED",
                "turn_legality": "UNKNOWN_NOT_RECORDED_AS_PROHIBITED"})
    result = pd.DataFrame(rows)
    if result.duplicated(["from_arc", "to_arc"]).any():
        raise ValueError("Duplicate inferred directed transition")
    return result


def asof_index(frame: pd.DataFrame, prediction_ns: int, *, age_ns: int = MAX_AGE_NS) -> int | None:
    """Latest usable speed with THREE independent temporal gates; null if missing.

    `frame` must be sorted by timestamp and contain usable/available_at/source
    watermark. The timestamp is a period end, NOT the availability timestamp.
    """
    if age_ns <= 0:
        raise ValueError("Age tolerance must be positive")
    observed = frame.timestamp.astype("int64").to_numpy()
    j = int(np.searchsorted(observed, prediction_ns, side="right")) - 1
    while j >= 0 and observed[j] >= prediction_ns - age_ns:
        r = frame.iloc[j]
        if (bool(r.usable) and pd.notna(r.speed_kmh) and pd.notna(r.available_at)
                and pd.notna(r.last_source_available_at)
                and int(r.available_at.value) <= prediction_ns
                and int(r.last_source_available_at.value) <= prediction_ns):
            return j
        j -= 1
    return None


def spatial_features(events: pd.DataFrame, paths: pd.DataFrame, bins_path: Path,
                     references: pd.DataFrame, *, bins_sha256: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return event x neighbor observation lineage and event aggregates.

    Reads each frozen-unit Parquet row group once. Latest as-of selection is per
    neighbor and event; never uses target detector (including its other lanes).
    Null speed/ratio/trend remains null, not zero. Reference fit ends before
    February 2023; ratios are only defined where a training-era reference exists.
    """
    if events.event_id.duplicated().any() or references.duplicated(KEY).any():
        raise ValueError("Duplicate event/reference")
    if paths.empty:
        raise ValueError("No inferred directed paths")
    chosen = paths.loc[paths.selected_path]
    relations = defaultdict(dict)
    for p in chosen.itertuples(index=False):
        a = (p.upstream_detector, p.upstream_direction, p.upstream_lane)
        b = (p.downstream_detector, p.downstream_direction, p.downstream_lane)
        if a[0] == b[0]:
            raise ValueError("Target detector cannot be its own neighbor")
        relations[(a, "downstream")][b[0]] = (b, p)
        relations[(b, "upstream")][a[0]] = (a, p)
    requests = defaultdict(list)
    for i, key in enumerate(events[KEY].itertuples(index=False, name=None)):
        for side in SIDES:
            for detector, (neighbor, path) in relations[(key, side)].items():
                requests[neighbor].append((i, side, path))
    parquet = pq.ParquetFile(bins_path)
    groups = {}
    for rg in range(parquet.num_row_groups):
        parts = []
        for field in KEY:
            stats = parquet.metadata.row_group(rg).column(parquet.schema_arrow.names.index(field)).statistics
            if stats is None or not stats.has_min_max or stats.min != stats.max:
                raise ValueError("Mixed-unit row group")
            parts.append(stats.min)
        key = tuple(parts)
        if key in groups:
            raise ValueError("Unit spans row groups")
        groups[key] = rg
    if set(requests) - groups.keys():
        raise ValueError("Neighbor bin unit missing")
    ref = {tuple(r[k] for k in KEY): (r.baseline_kmh, r.reference_fit_end)
           for _, r in references.iterrows()}
    details = []
    times = events.prediction_time.astype("int64").to_numpy()
    for key, demand in requests.items():
        frame = parquet.read_row_group(groups[key], columns=KEY + ["timestamp", "available_at",
            "last_source_available_at", "usable", "speed_kmh", "valid_slots"]).to_pandas()
        if not (frame[KEY] == pd.Series(key, index=KEY)).all().all():
            raise ValueError("Mixed-unit bins")
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        normal, fit_end = ref.get(key, (np.nan, pd.NaT))
        for i, side, path in demand:
            t = int(times[i]); j = asof_index(frame, t)
            if j is None:
                continue
            r = frame.iloc[j]
            if not (r.timestamp <= events.prediction_time.iloc[i]
                    and r.available_at <= events.prediction_time.iloc[i]
                    and r.last_source_available_at <= events.prediction_time.iloc[i]):
                raise ValueError("As-of gate failed")
            normal_ok = (pd.notna(normal) and normal > 0 and pd.notna(fit_end)
                and fit_end <= pd.Timestamp("2023-02-01", tz="Asia/Hong_Kong")
                and fit_end <= events.prediction_time.iloc[i])
            record = {"event_id": events.event_id.iloc[i], "target_detector": events.detector_id.iloc[i],
                "target_direction": events.direction.iloc[i], "target_lane": events.lane_id.iloc[i],
                "neighbor_detector": key[0], "neighbor_direction": key[1], "neighbor_lane": key[2],
                "side": side, "arc_sequence": path.arc_sequence, "route_sequence": path.route_sequence,
                "network_distance_m": path.path_distance_m, "path_alternatives": path.alternative_paths,
                "arc_count": path.arc_count,
                "mapping_tier": path.upstream_tier if side == "upstream" else path.downstream_tier,
                "population": path.population, "observed_at": r.timestamp, "available_at": r.available_at,
                "last_source_available_at": r.last_source_available_at,
                "source_sha256": bins_sha256, "age_minutes": (t - r.timestamp.value) / 60e9,
                "speed_kmh": float(r.speed_kmh), "speed_ratio": float(r.speed_kmh / normal) if normal_ok else np.nan,
                "valid_slot_fraction": r.valid_slots / 10}
            for minutes in (5, 10, 15):
                old = asof_index(frame, t - minutes * 60_000_000_000)
                record[f"change_{minutes}m_kmh"] = (float(r.speed_kmh - frame.iloc[old].speed_kmh)
                    if old is not None and frame.iloc[old].timestamp < r.timestamp else np.nan)
            details.append(record)
    detail = pd.DataFrame(details)
    if detail.empty:
        raise ValueError("No authentic as-of neighboring observations")
    if detail.duplicated(["event_id", "side", "neighbor_detector"]).any():
        raise ValueError("Multiple paths/lanes for one event-neighbor-side")
    rows = []
    by_event = dict(tuple(detail.groupby("event_id", sort=False)))
    for event in events.itertuples(index=False):
        group = by_event.get(event.event_id, detail.iloc[0:0])
        row = {"event_id": event.event_id, "prediction_time": event.prediction_time,
               "population": paths.population.iloc[0], "observed_neighbor_count": len(group)}
        for side in SIDES:
            g = group.loc[group.side.eq(side)]
            s = g.speed_kmh.to_numpy(dtype=float)
            ratios = g.speed_ratio.to_numpy(dtype=float)
            distance = g.network_distance_m.to_numpy(dtype=float)
            row[f"{side}_observed_count"] = len(g)
            row[f"{side}_missing"] = int(g.empty)
            row[f"{side}_mean_speed_kmh"] = float(np.mean(s)) if len(s) else np.nan
            row[f"{side}_mean_ratio"] = float(np.nanmean(ratios)) if np.isfinite(ratios).any() else np.nan
            row[f"{side}_congestion_fraction"] = float(np.mean(ratios[np.isfinite(ratios)] <= .5)) if np.isfinite(ratios).any() else np.nan
            row[f"{side}_mean_age_minutes"] = float(g.age_minutes.mean()) if len(g) else np.nan
            row[f"{side}_coverage"] = len(g) / len(relations[(event.detector_id,event.direction,event.lane_id),side]) if relations[(event.detector_id,event.direction,event.lane_id),side] else np.nan
            row[f"{side}_mean_network_distance_m"] = float(np.mean(distance)) if len(g) else np.nan
            weights = np.exp(-distance / 500)  # predeclared fixed 500m decay
            row[f"{side}_distance_weighted_speed"] = float(np.average(s, weights=weights)) if len(g) else np.nan
            confidence = np.where(g.mapping_tier.eq("HIGH_CONFIDENCE_INFERRED"), 1., .5)
            row[f"{side}_confidence_weighted_speed"] = float(np.average(s, weights=weights * confidence)) if len(g) else np.nan
            multihop = ratios[np.isfinite(ratios) & (g.arc_count.to_numpy(dtype=int) > 1)]
            row[f"{side}_multihop_congestion_fraction"] = float(np.mean(multihop <= .5)) if len(multihop) else np.nan
            for minutes in (5, 10, 15):
                row[f"{side}_change_{minutes}m_kmh"] = float(g[f"change_{minutes}m_kmh"].mean()) if g[f"change_{minutes}m_kmh"].notna().any() else np.nan
        row["upstream_downstream_congestion_difference"] = row["upstream_congestion_fraction"] - row["downstream_congestion_fraction"]
        row["local_minus_neighbor_ratio"] = event.speed_ratio - float(np.nanmean([row[f"{side}_mean_ratio"] for side in SIDES])) if any(pd.notna(row[f"{side}_mean_ratio"]) for side in SIDES) else np.nan
        row["neighbor_to_local_speed_gradient"] = (row["downstream_mean_speed_kmh"] - row["upstream_mean_speed_kmh"]) / (row["upstream_mean_network_distance_m"] + row["downstream_mean_network_distance_m"]) if all(pd.notna(row[f"{side}_mean_speed_kmh"]) and pd.notna(row[f"{side}_mean_network_distance_m"]) for side in SIDES) else np.nan
        row["local_neighbor_trend_difference"] = row["upstream_change_15m_kmh"] - row["downstream_change_15m_kmh"]
        rows.append(row)
    return detail, pd.DataFrame(rows)
