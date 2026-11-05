"""Past-only speed-trend and flow/occupancy features from the long-window release.

Reads the prepared long-window data directly from local parquet files
(no external `traffic_prepared.zip`), producing two feature tables that join
onto events on `event_id`:

- speed_history_features.parquet  (from cohort_bins.parquet, 5-minute bins)
- flow_occupancy_features.parquet (from cleaned-YYYYMMDD.parquet, 30-second rows)

Every feature is computed strictly from observations available at or before
`prediction_time` (leakage-safe). Adapted from Tianhao's
`experiments/tianhao/prepare_local.py`; the only change is sourcing the daily
cleaned rows from local parquet files instead of the packed zip.

Usage:
    uv run --locked python experiments/member4/prepare_features.py \
        --data-root D:/HK_Traffic_Recovery_Long_Window \
        --out-dir experiments/member4/prepared \
        --step all
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

KEY = ["detector_id", "direction", "lane_id"]


def load_events(data_root: Path) -> pd.DataFrame:
    events = pd.read_parquet(data_root / "processed/derived/events.parquet")
    return events.sort_values("prediction_time").reset_index(drop=True)


def speed_features(events: pd.DataFrame, data_root: Path, out_dir: Path) -> None:
    rows: list[dict] = []
    parquet = pq.ParquetFile(data_root / "processed/derived/cohort_bins.parquet")
    groups = {k: d for k, d in events.groupby(KEY)}
    seen: set = set()
    for rg in range(parquet.num_row_groups):
        part = parquet.read_row_group(
            rg,
            columns=KEY + ["timestamp", "available_at", "speed_kmh", "usable", "last_source_available_at"],
        ).to_pandas()
        for key, bins in part.groupby(KEY, sort=False):
            if key not in groups:
                continue
            assert key not in seen, "Lane spans multiple rowgroups; use a lane-level scanner instead"
            seen.add(key)
            bins = bins.sort_values("timestamp").set_index("timestamp")
            assert bins.index.is_unique
            for event in groups[key].itertuples():
                end = event.onset_confirmed_at
                index = pd.date_range(end - pd.Timedelta(minutes=15), end, freq="5min")
                window = bins.reindex(index)
                valid = (
                    window.usable.fillna(False).astype(bool)
                    & window.speed_kmh.notna()
                    & window.available_at.le(event.prediction_time)
                    & window.last_source_available_at.le(event.prediction_time)
                )
                ratio = window.speed_kmh.where(valid) / event.baseline_kmh
                complete = bool(valid.all())
                observed = window.loc[valid, "available_at"]
                rows.append({
                    "event_id": event.event_id,
                    "prediction_time": event.prediction_time,
                    "speed_change_15m_ratio": float(ratio.iloc[-1] - ratio.iloc[0]) if complete else np.nan,
                    "speed_mean_15m_ratio": float(ratio.mean()) if complete else np.nan,
                    "speed_slope_15m_ratio_per_min": float(np.polyfit(np.arange(4) * 5, ratio, 1)[0]) if complete else np.nan,
                    "speed_trend_observed_bins": int(valid.sum()),
                    "speed_trend_window_end": end,
                    "speed_trend_max_available_at": observed.max() if len(observed) else pd.NaT,
                })
        print(f"Speed rowgroup {rg + 1}/{parquet.num_row_groups}", flush=True)

    features = pd.DataFrame(rows)
    assert features.event_id.is_unique and set(features.event_id) == set(events.event_id)
    known = features.speed_trend_max_available_at.notna()
    assert (features.loc[known, "speed_trend_max_available_at"] <= features.loc[known, "prediction_time"]).all()
    features.to_parquet(out_dir / "speed_history_features.parquet", index=False)
    print("speed complete windows:", int(features.speed_change_15m_ratio.notna().sum()), flush=True)


def flow_features(events: pd.DataFrame, data_root: Path, out_dir: Path) -> None:
    events = events.copy()
    events["feature_date"] = events.onset_confirmed_at.dt.strftime("%Y%m%d")
    rows: list[dict] = []
    derived = data_root / "processed/derived"

    for j, (date, day_events) in enumerate(events.groupby("feature_date"), 1):
        member = derived / f"cleaned-{date}.parquet"
        daily = pd.read_parquet(member)

        crosses_midnight = (
            (day_events.onset_confirmed_at - pd.Timedelta(minutes=5)).dt.date
            .ne(day_events.onset_confirmed_at.dt.date)
            .any()
        )
        if crosses_midnight:
            previous = (pd.Timestamp(date) - pd.Timedelta(days=1)).strftime("%Y%m%d")
            prior = pd.read_parquet(derived / f"cleaned-{previous}.parquet")
            daily = pd.concat([prior, daily], ignore_index=True)
            assert not daily.duplicated(KEY + ["timestamp"]).any(), "Unexpected overlap between cleaned day partitions"

        available_col = "available_at" if "available_at" in daily else "archive_time"
        if available_col not in daily:
            raise ValueError("Cannot verify raw measurement availability")

        by_unit = {k: d for k, d in daily.groupby(KEY, sort=False)}
        for event in day_events.itertuples():
            local = by_unit.get(tuple((getattr(event, k) for k in KEY)), daily.iloc[:0])
            window = local.loc[
                (local.timestamp > event.onset_confirmed_at - pd.Timedelta(minutes=5))
                & local.timestamp.le(event.onset_confirmed_at)
                & local[available_col].le(event.prediction_time)
            ]
            observed = window.loc[window.source_valid] if "source_valid" in window else window
            invalid = ~observed.valid.eq("Y") | observed.conflict.fillna(False).astype(bool)
            assert observed.loc[invalid, ["volume_count", "occupancy_pct"]].isna().all().all()
            volume = pd.to_numeric(observed.volume_count, errors="coerce").dropna()
            occupancy = pd.to_numeric(observed.occupancy_pct, errors="coerce").dropna()
            populated = observed.loc[observed.volume_count.notna() | observed.occupancy_pct.notna()]
            rows.append({
                "event_id": event.event_id,
                "prediction_time": event.prediction_time,
                "volume_median_per_observed_30s": float(volume.median()) if len(volume) else np.nan,
                "occupancy_median_pct": float(occupancy.median()) if len(occupancy) else np.nan,
                "flow_observed_slots": int(len(volume)),
                "occupancy_observed_slots": int(len(occupancy)),
                "flow_max_available_at": populated[available_col].max() if len(populated) else pd.NaT,
            })
        if j % 200 == 0:
            print(f"Flow/occupancy {j} days; {len(rows)} events", flush=True)

    features = pd.DataFrame(rows)
    assert features.event_id.is_unique and len(features) == len(events)
    known = features.flow_max_available_at.notna()
    assert (features.loc[known, "flow_max_available_at"] <= features.loc[known, "prediction_time"]).all()
    features.to_parquet(out_dir / "flow_occupancy_features.parquet", index=False)
    print("Flow/occupancy features:", features.shape, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--step", choices=["speed", "flow", "all"], default="all")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(args.data_root)

    if args.step in ("speed", "all"):
        speed_features(events, args.data_root, args.out_dir)
    if args.step in ("flow", "all"):
        flow_features(events, args.data_root, args.out_dir)


if __name__ == "__main__":
    main()
