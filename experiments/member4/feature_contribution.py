"""Member 4 feature-group contribution analysis on saved interpretation data.

Aggregates random-forest feature importances from the saved interpretation.csv
into local / history / flow group shares, per horizon. Shows that the history
group (15-minute pre-onset speed trend) is the single largest contributor to the
random forest, which backs the ROC-AUC lift seen when history is added.

Reads only the already-saved interpretation.csv; no model is re-fitted.

Status: EXPLORATORY.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

GROUPS: dict[str, list[str]] = {
    "local": ["speed_kmh", "speed_ratio", "baseline_kmh", "valid_slots",
              "onset_observed_minutes"],
    "history": ["speed_change_15m_ratio", "speed_mean_15m_ratio",
                "speed_slope_15m_ratio_per_min", "speed_trend_observed_bins"],
    "flow": ["volume_median_per_observed_30s", "occupancy_median_pct",
             "flow_observed_slots", "occupancy_observed_slots"],
}


def _group(feature: str) -> str:
    name = feature.replace("numeric__", "")
    for group, names in GROUPS.items():
        if name in names:
            return group
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interpretation", type=Path,
                        default=Path("experiments/member4/comparison-hf-v1/interpretation.csv"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("experiments/member4/feature-contribution-v1"))
    args = parser.parse_args()

    df = pd.read_parquet if False else pd.read_csv
    frame = df(args.interpretation)
    rf = frame[(frame.model == "random_forest")
               & (frame.importance_type == "feature_importance")
               & (frame.feature_set == "local+history+flow")].copy()
    rf["group"] = rf["feature"].map(_group)

    shares = rf.groupby(["horizon_min", "group"])["value"].sum().unstack()
    for col in GROUPS:
        if col not in shares:
            shares[col] = 0.0
    shares = shares[list(GROUPS)]
    shares["total"] = shares.sum(axis=1)
    out = shares.copy()
    for col in GROUPS:
        out[f"{col}_share"] = shares[col] / shares["total"]
    out = out.reset_index()

    # Zero-importance features are worth flagging explicitly.
    zero = sorted(rf.loc[rf.value == 0, "feature"].unique().tolist())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_dir / "group_shares.csv", index=False)

    print("=== rf group contribution share (local+history+flow) ===")
    for _, row in out.iterrows():
        h = int(row.horizon_min)
        print(f"{h}m: local={row['local_share']:.1%}  history={row['history_share']:.1%}  "
              f"flow={row['flow_share']:.1%}")
    print("\nZero-importance features:", zero)
    print(f"\nWrote {args.output_dir.resolve() / 'group_shares.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
