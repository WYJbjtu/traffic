"""Real as-of candidate opportunity, separated from approved spatial eligibility."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from traffic_recovery.network.spatial_features import neighbor_features
from traffic_recovery.network.spatial96 import UNIT

MAX_AGE = pd.Timedelta(minutes=10)


def candidate_opportunity(events: pd.DataFrame, paths: pd.DataFrame, bins_path: Path,
                          references: pd.DataFrame) -> pd.DataFrame:
    """Examine only candidate neighbor lanes, never produce model-approved features.

    One bounded Parquet row group per frozen unit. Uses both bin closure and raw
    source watermark <= prediction time and never imputes missing speeds. Latest
    eligible bin within 10 minutes is chosen separately per detector.
    """
    if events.event_id.duplicated().any() or events[UNIT].isna().any().any():
        raise ValueError("Duplicate event or missing lane identity")
    if paths.empty:
        pairs = pd.DataFrame(columns=["upstream_detector","upstream_direction","upstream_lane",
            "downstream_detector","downstream_direction","downstream_lane"])
    else:
        pairs = paths[["upstream_detector","upstream_direction","upstream_lane","downstream_detector",
                       "downstream_direction","downstream_lane"]].drop_duplicates()
    relations: dict[tuple, dict[str, set[tuple]]] = defaultdict(lambda: {"upstream": set(), "downstream": set()})
    for p in pairs.itertuples(index=False):
        a, b = (p.upstream_detector,p.upstream_direction,p.upstream_lane), (p.downstream_detector,p.downstream_direction,p.downstream_lane)
        if a[0] != b[0]:
            relations[a]["downstream"].add(b)
            relations[b]["upstream"].add(a)
    # Request index for each neighbor unit, built once instead of scanning the
    # 35.8m-row Parquet separately for each event.
    requested: dict[tuple, list[tuple[int,str]]] = defaultdict(list)
    keys = list(events[UNIT].itertuples(index=False, name=None))
    for i, key in enumerate(keys):
        for side in ("upstream", "downstream"):
            for neighbor in relations[key][side]:
                requested[neighbor].append((i, side))
    result: dict[tuple[int,str], list[dict]] = defaultdict(list)
    parquet = pq.ParquetFile(bins_path)
    groups = {}
    for rg in range(parquet.num_row_groups):
        metadata = parquet.metadata.row_group(rg)
        key_parts = []
        for col in UNIT:
            index = parquet.schema_arrow.names.index(col)
            stats = metadata.column(index).statistics
            if stats is None or not stats.has_min_max or stats.min != stats.max:
                raise ValueError("Row group is not single-unit; bounded index unavailable")
            key_parts.append(stats.min)
        key = tuple(key_parts)
        if key in groups:
            raise ValueError("Unit spans row groups: bounded read needs new unit index")
        groups[key] = rg
    if set(requested) - set(groups):
        raise ValueError(f"Candidate neighbor absent from Release bins: {set(requested) - set(groups)}")
    reference = {tuple(r[c] for c in UNIT): (r.baseline_kmh,r.reference_fit_end)
        for _,r in references.iterrows()}
    if references.duplicated(UNIT).any():
        raise ValueError("Duplicate reference unit")
    times = events.prediction_time.astype("int64").to_numpy()
    max_age_ns = int(MAX_AGE.value)
    for key, requests in requested.items():
        table = parquet.read_row_group(groups[key], columns=UNIT + ["timestamp", "available_at",
            "last_source_available_at", "usable", "speed_kmh", "valid_slots", "present_slots"]).to_pandas()
        if not (table[UNIT] == pd.Series(key,index=UNIT)).all().all():
            raise ValueError(f"Mixed-unit Parquet row group: {key}")
        table = table.loc[table.usable.fillna(False) & table.speed_kmh.notna()
            & table.available_at.notna() & table.last_source_available_at.notna()].sort_values("timestamp")
        observed = table.timestamp.astype("int64").to_numpy()
        available = table.available_at.astype("int64").to_numpy()
        raw_available = table.last_source_available_at.astype("int64").to_numpy()
        speed = table.speed_kmh.to_numpy(dtype=float)
        valid = table.valid_slots.to_numpy(dtype=int)
        present = table.present_slots.to_numpy(dtype=int)
        for i, side in requests:
            t = times[i]; j = int(np.searchsorted(observed, t, side="right")) - 1
            while j >= 0 and observed[j] >= t-max_age_ns and (available[j] > t or raw_available[j] > t):
                j -= 1
            if j < 0 or observed[j] < t-max_age_ns:
                result[i,side].append({"neighbor": key, "reason": "no_usable_asof_bin_within_10m"})
                continue
            baseline, fit_end = reference.get(key, (np.nan, pd.NaT))
            ref_ok = (pd.notna(baseline) and baseline > 0 and pd.notna(fit_end)
                and fit_end <= pd.Timestamp("2023-02-01",tz="Asia/Hong_Kong")
                and fit_end <= events.prediction_time.iloc[i])
            result[i,side].append({"neighbor": key, "reason": "observed", "timestamp": observed[j],
                "available_at": available[j], "speed_kmh": speed[j], "age_minutes": (t-observed[j])/60e9,
                "reference_available": bool(ref_ok), "valid_slots": int(valid[j]),
                "present_slots": int(present[j])})
    rows = []
    for i,event in enumerate(events.itertuples(index=False)):
        row = {"event_id": event.event_id, "prediction_time": event.prediction_time,
            "split": event.split_proposal, "label_known_30m": pd.notna(event.label_30m),
            "feature_status": "CANDIDATE_ONLY_NOT_MODEL_APPROVED"}
        for side in ("upstream", "downstream"):
            records = result.get((i,side), [])
            found = [r for r in records if r["reason"] == "observed"]
            # A detector contributes at most once per direction. Multiple lanes
            # on one detector cannot be treated as independent road observations.
            per_detector = {}
            for record in found:
                detector = record["neighbor"][0]
                if detector not in per_detector or record["timestamp"] > per_detector[detector]["timestamp"]:
                    per_detector[detector] = record
            found = sorted(per_detector.values(),key=lambda r:r['timestamp'],reverse=True)
            row.update({f"{side}_candidate_detectors": len({r['neighbor'][0] for r in records}),
                f"{side}_available_speed_count": len(found),
                f"{side}_latest_speed_kmh": found[0]["speed_kmh"] if found else np.nan,
                f"{side}_minimum_age_minutes": min((r["age_minutes"] for r in found), default=np.nan),
                f"{side}_latest_available_at": pd.Timestamp(max(r["available_at"] for r in found),tz="Asia/Hong_Kong") if found else pd.NaT,
                f"{side}_reference_detectors": sum(r["reference_available"] for r in found),
                f"{side}_mean_valid_slot_fraction": float(np.mean([r["valid_slots"]/10 for r in found])) if found else np.nan,
                f"{side}_mean_present_slot_fraction": float(np.mean([r["present_slots"]/10 for r in found])) if found else np.nan,
                f"{side}_missing_reason": "no_candidate_directed_pair" if not records else "no_usable_asof_bin_within_10m" if not found else "observed"})
        row["valid_observed_neighbor_detector_count"] = row["upstream_available_speed_count"] + row["downstream_available_speed_count"]
        rows.append(row)
    return pd.DataFrame(rows)


def verified_zero_eligibility(events: pd.DataFrame, references: pd.DataFrame,
                              *, version: str) -> pd.DataFrame:
    """Call the fail-closed production feature gate with no approved relationships."""
    empty_mapping = pd.DataFrame(columns=UNIT + ["arc_id","review_status","reviewer","valid_from","valid_to","network_version"])
    empty_graph = pd.DataFrame(columns=["from_arc","to_arc","review_status","reviewer","valid_from","valid_to","network_version"])
    empty_bins = pd.DataFrame({col:pd.Series(dtype="datetime64[ns, Asia/Hong_Kong]") for col in ["timestamp","available_at"]})
    for col in UNIT: empty_bins[col] = pd.Series(dtype="string")
    empty_bins["usable"] = pd.Series(dtype=bool)
    empty_bins["speed_kmh"] = pd.Series(dtype=float)
    reference_cutoff = pd.Timestamp("2023-02-01",tz="Asia/Hong_Kong")
    output = []
    for start in range(0, len(events), 512):
        output.append(neighbor_features(events.iloc[start:start+512],empty_mapping,empty_graph,empty_bins,
            references,network_version=version,reference_cutoff=reference_cutoff,max_age=MAX_AGE))
    result = pd.concat(output,ignore_index=True)
    result["split"] = events.split_proposal.to_numpy()
    result["label_known_30m"] = events.label_30m.notna().to_numpy()
    result["spatial_model_eligible"] = (result.upstream_observed_detectors + result.downstream_observed_detectors > 0)
    if result.spatial_model_eligible.any():
        raise ValueError("Unapproved candidate produced model eligibility")
    return result
