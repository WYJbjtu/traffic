"""Reconstruct and export paired P1 test comparisons from authenticated saved scores.

uv run --locked python -m experiments.unified96.analyze --out reports/final_research
Refuses to overwrite any existing generated CSV. The previously inspected test
set makes this analysis retrospective, not new blind validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, log_loss

from traffic_recovery.data.http import sha256_file
from experiments.unified96.run import ROOT, event_hash

RUN = ROOT / "experiments/unified96/runs/p1-f0-f4-v1"


def analyze(out: Path) -> None:
    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["outputs_sha256"].items():
        if sha256_file(RUN / name) != digest:
            raise ValueError(f"Run file changed: {name}")
    pred = pd.read_parquet(RUN / "predictions.parquet")
    metrics = pd.read_csv(RUN / "metrics.csv")
    bootstrap = json.loads((RUN / "paired_bootstrap.json").read_text(encoding="utf-8"))
    if pred.duplicated(["event_id", "split", "model", "feature_arm"]).any():
        raise ValueError("Duplicate saved prediction identity")
    for row in metrics.itertuples():
        block = pred.loc[pred.model.eq(row.model) & pred.split.eq(row.split) & pred.feature_arm.eq(row.arm)]
        if (len(block) != row.n_events or event_hash(block.event_id) != row.event_ids_sha256 or
            int(block.y_true.sum()) != row.n_positive or
            not np.isclose(roc_auc_score(block.y_true, block.y_score), row.roc_auc) or
            not np.isclose(average_precision_score(block.y_true, block.y_score), row.average_precision) or
            not np.isclose(log_loss(block.y_true, block.y_score), row.log_loss)):
            raise ValueError(f"Saved metrics cannot be reconstructed: {row.model}/{row.arm}/{row.split}")
    gain, errors = [], []
    for record in bootstrap:
        model = record["model"]
        subset = pred.loc[pred.model.eq(model) & pred.split.eq("test")]
        left = subset.loc[subset.feature_arm.eq("F0")]
        right = subset.loc[subset.feature_arm.eq("F4")]
        paired = left.merge(right, on=["event_id", "prediction_time", "detector_id", "split",
                  "target_version", "horizon_min", "population", "model", "y_true"],
                  suffixes=("_f0", "_f4"), how="outer", validate="one_to_one", indicator=True)
        if len(paired) != manifest["split_counts"]["test"] or not paired._merge.eq("both").all():
            raise ValueError("Event-level predictions not paired")
        roc = record["roc_auc"]
        gain.append({"population": "P1_INFERRED_EXPLORATORY", "target_version": manifest["target"],
                     "horizon_min": 30, "split": "test", "n_events": len(paired), "clusters": record["clusters"],
                     "model": model, "comparison": "F4_minus_F0", "delta_roc_auc": roc["observed_delta"],
                     "ci_95_lower": roc["ci_95_percentile"][0], "ci_95_upper": roc["ci_95_percentile"][1],
                     "valid_resamples": roc["valid_resamples"], "invalid_single_class": record["invalid_single_class"],
                     "delta_pr_auc": record["average_precision"]["observed_delta"]})
        state = np.select([paired.y_pred_f0.eq(paired.y_true) & paired.y_pred_f4.eq(paired.y_true),
                           paired.y_pred_f0.ne(paired.y_true) & paired.y_pred_f4.ne(paired.y_true),
                           paired.y_pred_f0.ne(paired.y_true) & paired.y_pred_f4.eq(paired.y_true)],
                          ["both_correct", "both_wrong", "only_spatial_correct"], default="only_base_correct")
        counts = pd.Series(state).value_counts()
        errors.append({"model": model, "population": "P1_INFERRED_EXPLORATORY", "split": "test",
                       "target_version": manifest["target"], "horizon_min": 30, "n_events": len(paired),
                       **{name: int(counts.get(name, 0)) for name in
                          ("both_correct", "both_wrong", "only_spatial_correct", "only_base_correct")},
                       "mean_delta_probability_y1": float((paired.loc[paired.y_true.eq(1),"y_score_f4"] - paired.loc[paired.y_true.eq(1),"y_score_f0"]).mean()),
                       "mean_delta_probability_y0": float((paired.loc[paired.y_true.eq(0),"y_score_f4"] - paired.loc[paired.y_true.eq(0),"y_score_f0"]).mean())})
    out.mkdir(parents=True, exist_ok=True)
    for name, table in (("spatial_marginal_gain.csv", pd.DataFrame(gain)),
                        ("error_transitions.csv", pd.DataFrame(errors))):
        path = out / name
        if path.exists():
            raise FileExistsError(f"Refusing overwrite: {path}")
        table.to_csv(path, index=False)


def build_matrix(path: Path) -> None:
    """List actual four-model × eight-arm statuses; do not manufacture C/W metrics."""
    if path.exists():
        raise FileExistsError(f"Refusing overwrite: {path}")
    metrics = pd.read_csv(RUN / "metrics.csv")
    rows = []
    for model in ("logistic_regression", "random_forest", "xgboost", "hist_gradient_boosting"):
        for index in range(8):
            arm = f"F{index}"
            selected = metrics.loc[metrics.model.eq(model) & metrics.arm.eq(arm) & metrics.split.eq("test")]
            if len(selected) > 1:
                raise ValueError("Duplicate model/arm metric")
            record = {"model": model, "arm": arm, "population": "P1_INFERRED_EXPLORATORY",
                      "target_version": "recovery_confirmation_v1", "horizon_min": 30,
                      "split": "test", "status": "EXECUTED" if len(selected) else "BLOCKED_MISSING_C_W",
                      "n_events": int(selected.iloc[0].n_events) if len(selected) else None,
                      "event_ids_sha256": selected.iloc[0].event_ids_sha256 if len(selected) else None,
                      "roc_auc": float(selected.iloc[0].roc_auc) if len(selected) else None}
            rows.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    analyze(parser.parse_args().out)


if __name__ == "__main__":
    main()
