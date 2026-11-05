"""Build the model dataset for the history+flow experiment.

Merges the speed-history and flow/occupancy feature tables onto the long-window
events, normalises the split column, fills unavailable flow timestamps with the
prediction time (so the availability column stays non-null and timezone-aware),
then builds the model dataset through the shared `build_model_dataset` and
writes the parquet + manifest (mirroring `build_model_dataset_files`).

Usage:
    uv run --locked python experiments/member4/build_dataset_hf.py \
        --data-root D:/HK_Traffic_Recovery_Long_Window \
        --prepared experiments/member4/prepared \
        --contract experiments/member4/experiment_contract_hf.json \
        --output experiments/member4/event_features_hf.parquet \
        --manifest experiments/member4/model-dataset-manifest-hf.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from traffic_recovery.data.http import sha256_file
from traffic_recovery.models.contract import ExperimentContract
from traffic_recovery.models.dataset import build_model_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    for target in (args.output, args.manifest):
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing artifact: {target}")

    frame = pd.read_parquet(args.data_root / "processed/derived/events.parquet")
    inputs = {
        "events": {
            "path": (args.data_root / "processed/derived/events.parquet").as_posix(),
            "sha256": sha256_file(args.data_root / "processed/derived/events.parquet"),
        }
    }
    for name in ["speed_history_features", "flow_occupancy_features"]:
        path = args.prepared / (name + ".parquet")
        feature = pd.read_parquet(path)
        assert set(frame.event_id) == set(feature.event_id) and feature.event_id.is_unique
        overlap = set(frame.columns) & set(feature.columns) - {"event_id", "prediction_time"}
        assert not overlap, f"Unexpected column overlap: {overlap}"
        frame = frame.merge(feature, on=["event_id", "prediction_time"], how="left", validate="one_to_one")
        inputs[name] = {"path": path.as_posix(), "sha256": sha256_file(path)}

    frame["split"] = frame.split_proposal.astype("string")
    frame["flow_max_available_at"] = frame["flow_max_available_at"].fillna(frame["prediction_time"])

    for columns in [
        ["speed_kmh", "speed_ratio", "baseline_kmh", "valid_slots", "onset_observed_minutes"],
        ["speed_change_15m_ratio", "speed_mean_15m_ratio", "speed_slope_15m_ratio_per_min", "speed_trend_observed_bins"],
        ["volume_median_per_observed_30s", "occupancy_median_pct", "flow_observed_slots", "occupancy_observed_slots"],
    ]:
        for col in columns:
            frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)

    contract = ExperimentContract.from_path(args.contract)
    dataset, report = build_model_dataset(frame, contract)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(args.output, index=False)
    manifest = {
        "manifest_version": "model-dataset-manifest-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "validation": report,
        "inputs": inputs,
        "contract": {"path": args.contract.as_posix(), "sha256": sha256_file(args.contract)},
        "output": {"path": args.output.as_posix(), "sha256": sha256_file(args.output)},
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("dataset written:", args.output)
    print("rows:", len(dataset))
    print("feature_groups:", report["feature_groups"])


if __name__ == "__main__":
    main()
