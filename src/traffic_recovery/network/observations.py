"""Fail-closed, provenance-preserving as-of neighbor speed interface.

Candidate network arcs are never eligible as verified neighbors. Callers must
supply human-reviewed arc/route mappings and transitions separately; this
adapter only selects observations for already-verified neighboring segment IDs.
"""
from __future__ import annotations

import pandas as pd


def neighbor_speeds(neighbor_ids: list[str], prediction_time: pd.Timestamp,
                    processed: pd.DataFrame, raw_mapped: pd.DataFrame,
                    *, network_version: str, max_age: pd.Timedelta = pd.Timedelta(minutes=10)) -> pd.DataFrame:
    """Return one row per eligible neighbor, raw preferred but both retained.

    Both input tables need segment_id, observed_at, available_at, speed_kmh,
    network_version, review_status and provenance. Processed inputs additionally
    need valid/source_type/usable_for_historical_features. Raw input is mapped
    only by a human-reviewed same-version mapping; raw source is independent as
    a *table*, not necessarily independent of processed source. Missing speed is
    nullable; zero is retained. No retrospective fallbacks or nearest matches.
    """
    if prediction_time.tzinfo is None or max_age <= pd.Timedelta(0):
        raise ValueError("Aware prediction_time and positive max_age required")
    required = {"segment_id", "observed_at", "available_at", "speed_kmh",
                "network_version", "review_status", "source_hash"}
    for table in (processed, raw_mapped):
        if not required <= set(table):
            raise ValueError(f"Missing observation columns: {sorted(required - set(table))}")
        for col in ("observed_at", "available_at"):
            if not isinstance(table[col].dtype, pd.DatetimeTZDtype):
                raise ValueError(f"{col} must be timezone-aware")
        if (table.available_at < table.observed_at).any():
            raise ValueError("Availability before observation")
    if not {"valid", "source_type", "usable_for_historical_features"} <= set(processed):
        raise ValueError("Processed source validity/provenance/approval missing")
    if processed.source_type.ne("official_processed_segment").any():
        raise ValueError("Incorrect processed source type")
    if len(set(neighbor_ids)) != len(neighbor_ids):
        raise ValueError("Duplicate eligible neighbor IDs")

    def latest(table: pd.DataFrame, kind: str) -> pd.DataFrame:
        eligible = table.loc[table.segment_id.isin(neighbor_ids)
            & table.review_status.eq("human_verified")
            & table.network_version.eq(network_version)
            & table.observed_at.le(prediction_time)
            & table.available_at.le(prediction_time)
            & table.observed_at.ge(prediction_time - max_age)
            & table.speed_kmh.notna()].copy()
        if kind == "processed":
            eligible = eligible.loc[eligible.valid.eq("Y") & eligible.usable_for_historical_features.eq(True)]
        eligible = eligible.sort_values(["observed_at", "available_at", "source_hash"])
        return eligible.drop_duplicates("segment_id", keep="last").set_index("segment_id")

    raw = latest(raw_mapped, "raw")
    proxy = latest(processed, "processed")
    rows = []
    for rid in neighbor_ids:
        r = raw.loc[rid] if rid in raw.index else None
        p = proxy.loc[rid] if rid in proxy.index else None
        chosen = r if r is not None else p
        rows.append({"segment_id": rid,
            "speed_kmh": chosen.speed_kmh if chosen is not None else pd.NA,
            "source_type": ("raw_detector_observed" if r is not None else
                            "official_processed_segment" if p is not None else "unavailable"),
            "raw_speed_kmh": r.speed_kmh if r is not None else pd.NA,
            "processed_speed_kmh": p.speed_kmh if p is not None else pd.NA,
            "raw_source_hash": r.source_hash if r is not None else None,
            "processed_source_hash": p.source_hash if p is not None else None,
            "observed_at": chosen.observed_at if chosen is not None else pd.NaT,
            "available_at": chosen.available_at if chosen is not None else pd.NaT,
            "possible_source_dependence": bool(r is not None and p is not None)})
    return pd.DataFrame(rows)
