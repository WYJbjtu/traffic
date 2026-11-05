"""Member 4 error analysis on saved long-window predictions.

Recomputes confusion matrices, class-imbalance-aware metrics and a per-arm
prevalence breakdown from the already-saved predictions in comparison-hf-v1,
without re-fitting any model. Flags the horizon-dependent class imbalance that
the ROC-AUC headline alone obscures.

Status: EXPLORATORY. No scientific conclusion is claimed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from traffic_recovery.models.saved_comparison import compare_saved_runs


def _load_one(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path,
                        default=Path("experiments/member4/comparison-hf-v1/predictions.parquet"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("experiments/member4/error-analysis-v1"))
    args = parser.parse_args()

    pred = _load_one(args.predictions)
    # compare_saved_runs expects a mapping of experiment name -> frame.
    metrics, confusion, pairing = compare_saved_runs({"long_window": pred})

    # Restrict the headline tables to the test split, which is the only honest
    # evaluation set. train/validation rows remain in the full export.
    test_metrics = metrics[metrics.split == "test"].copy()
    test_confusion = confusion[confusion.split == "test"].copy()

    # Per-arm prevalence so the class imbalance is explicit.
    test_metrics["prevalence"] = test_metrics.n_positive / test_metrics.n_rows

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output_dir / "metrics_all_splits.csv", index=False)
    test_metrics.to_csv(args.output_dir / "test_metrics.csv", index=False)
    test_confusion.to_csv(args.output_dir / "test_confusion.csv", index=False)
    pairing.to_csv(args.output_dir / "pairing_audit.csv", index=False)

    # Compact console summary of the imbalance story.
    keep = ["feature_set", "model", "horizon_min", "roc_auc", "pr_auc",
            "precision", "recall", "f1", "balanced_accuracy", "n_positive", "n_rows"]
    view = test_metrics[keep].sort_values(["horizon_min", "feature_set", "model"])
    print("=== test-split metrics (imbalance-aware) ===")
    print(view.round(3).to_string(index=False))
    print()
    print("=== test-split confusion (tn/fp/fn/tp) ===")
    print(test_confusion.sort_values(["horizon_min", "feature_set", "model"]).to_string(index=False))
    print()
    print(f"Wrote artifacts to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
