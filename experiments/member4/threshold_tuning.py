"""Member 4 threshold tuning on saved long-window predictions.

For each (horizon, feature_set, model) arm the decision threshold is selected
on the validation split only, then applied to the test split. Selection uses
Youden's J (maximising balanced accuracy) on validation probability scores.
The fixed 0.5 threshold used in the original run is shown alongside.

Status: EXPLORATORY.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)


def _youden_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Pick the threshold maximising balanced accuracy on the given fold."""
    order = np.argsort(y_score)
    ys = y_score[order]
    yt = y_true[order]
    # Candidate thresholds at midpoints between consecutive distinct scores.
    uniq, idx = np.unique(ys, return_index=True)
    best_t, best_j = 0.5, -1.0
    for i in range(len(uniq) - 1):
        t = (uniq[i] + uniq[i + 1]) / 2.0
        pred = ys >= t
        tp = int(np.sum(pred & (yt == 1)))
        fn = int(np.sum(~pred & (yt == 1)))
        tn = int(np.sum(~pred & (yt == 0)))
        fp = int(np.sum(pred & (yt == 0)))
        tpr = tp / (tp + fn) if (tp + fn) else 0.0
        tnr = tn / (tn + fp) if (tn + fp) else 0.0
        j = tpr + tnr - 1.0
        if j > best_j:
            best_j, best_t = j, t
    return float(best_t)


def _metrics(y_true, y_pred, y_score):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "roc_auc": roc_auc_score(y_true, y_score),
        "pr_auc": average_precision_score(y_true, y_score),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path,
                        default=Path("experiments/member4/comparison-hf-v1/predictions.parquet"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("experiments/member4/threshold-tuning-v1"))
    args = parser.parse_args()

    df = pd.read_parquet(args.predictions)
    # Only probability-based models can be threshold-tuned; rule scores and
    # majority/prevalence baselines have no meaningful probability curve.
    prob = df[df.score_kind == "probability"].copy()

    arms = ["horizon_min", "feature_set", "model"]
    rows = []
    for key, arm in prob.groupby(arms, sort=True):
        val = arm[arm.split == "validation"]
        tst = arm[arm.split == "test"]
        if val.empty or tst.empty:
            continue
        t_opt = _youden_threshold(val.y_true.to_numpy(), val.y_score.to_numpy())
        # Apply to test with tuned threshold and with the original 0.5.
        tuned_pred = (tst.y_score.to_numpy() >= t_opt).astype(int)
        base_pred = (tst.y_score.to_numpy() >= 0.5).astype(int)
        base = _metrics(tst.y_true.to_numpy(), base_pred, tst.y_score.to_numpy())
        tuned = _metrics(tst.y_true.to_numpy(), tuned_pred, tst.y_score.to_numpy())
        rows.append({"horizon_min": key[0], "feature_set": key[1], "model": key[2],
                     "threshold": 0.5, **base})
        rows.append({"horizon_min": key[0], "feature_set": key[1], "model": key[2],
                     "threshold": round(t_opt, 4), **tuned})

    out = pd.DataFrame(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_dir / "threshold_comparison.csv", index=False)

    # Compact console view: balanced_accuracy and recall at 15m, specificity at 60m.
    view = out.sort_values(["horizon_min", "feature_set", "model", "threshold"])
    print("=== threshold comparison (0.5 vs validation-tuned), test split ===")
    cols = ["horizon_min", "feature_set", "model", "threshold",
            "balanced_accuracy", "recall", "precision", "f1", "tn", "fp", "fn", "tp"]
    print(view[cols].round(3).to_string(index=False))
    print(f"\nWrote {args.output_dir.resolve() / 'threshold_comparison.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
