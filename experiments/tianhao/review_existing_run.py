"""Read-only checks of a trusted local run against the current review fixes.

No training or downloads. Model files are verified against the original run
manifest before loading; use only the team's own trusted local run directory.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from traffic_recovery.external.calendar import calendar_features
from traffic_recovery.models.contract import ExperimentContract, validate_event_table
from traffic_recovery.models.evaluation import evaluate_predictions


def review(run: Path, prepared: Path) -> dict[str, object]:
    """Verify saved bytes, labels, availability, fitted transforms and predictions."""
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    checks = 0

    def check(condition: object, description: str) -> None:
        nonlocal checks
        if not bool(condition):
            raise AssertionError(description)
        checks += 1

    for name, expected in manifest["outputs"].items():
        with (run / name).open("rb") as stream:
            check(hashlib.file_digest(stream, "sha256").hexdigest() == expected,
                  "Historical output SHA256: " + name)
    frame = pd.read_parquet(run / "event_feature_audit.parquet")
    pred = pd.read_parquet(run / "predictions.parquet")
    contract = ExperimentContract.from_path(run / "experiment_contract.json")
    validation = validate_event_table(frame, replace(contract, horizons=(15, 30, 60)))
    check(validation["rows"] == 7597, "Original event cohort")
    for split, end in [("train", contract.validation_start),
                       ("validation", contract.test_start), ("test", contract.test_end)]:
        part = frame.loc[frame.split.eq(split)]
        check(part.outcome_maturity_at.notna().all()
              and part.outcome_maturity_at.lt(end).all(), "Outcome maturity: " + split)
    for kind, value in [("temperature", "temperature_c"), ("wind", "wind_speed_kmh")]:
        known = frame[value].notna()
        check(frame.loc[known, kind + "_available_at"].le(frame.loc[known, "prediction_time"]).all(),
              "Weather availability: " + kind)
        check(frame.loc[known, kind + "_observed_at"].le(frame.loc[known, "prediction_time"]).all(),
              "Weather observation time: " + kind)
        check(frame.loc[known, kind + "_age_minutes"].between(0, 60).all(),
              "Weather age: " + kind)

    holidays = pd.read_parquet(prepared / "official_holiday_editions.parquet")
    updated = calendar_features(frame[["event_id", "prediction_time"]], holidays)
    updated = updated.set_index("event_id").loc[frame.event_id]
    calendar_changes = {}
    for column in contract.feature_groups["calendar"]:
        before = frame[column].to_numpy(dtype=float, na_value=np.nan)
        after = pd.to_numeric(updated[column]).to_numpy(dtype=float, na_value=np.nan)
        calendar_changes[column] = int((~np.isclose(before, after, equal_nan=True)).sum())
    check(not any(calendar_changes.values()), "No historical calendar feature values changed")

    table = pd.read_csv(run / "metrics_summary.csv").set_index(["model", "feature_set", "split"])
    metrics = evaluate_predictions(pred, version_column="experiment_version")
    for row in metrics.itertuples():
        actual = table.loc[(row.model, row.feature_set, row.split), row.metric_name]
        check(np.isclose(actual, row.metric_value, equal_nan=True), "Saved metric: " + row.metric_name)

    # The fitted object hash was checked above before deserializing trusted files.
    check("fitted_pipelines.joblib" in manifest["outputs"], "Fitted model checksum is present")
    fitted = joblib.load(run / "fitted_pipelines.joblib")
    plan = json.loads((run / "predeclared_plan.json").read_text(encoding="utf-8"))
    checked_predictions = 0
    for (kind, feature_set), pipeline in fitted.items():
        columns = [name for group in feature_set.split("+") for name in plan["feature_groups"][group]]
        train = frame.loc[frame.split.eq("train") & frame.label_30m.notna(), columns]
        numeric = pipeline.named_steps["preprocess"].named_transformers_["numeric"]
        imputer = numeric.named_steps["impute"]
        check(np.allclose(imputer.statistics_, train.median().to_numpy(), equal_nan=True),
              "Training-only imputation: " + feature_set)
        if kind == "logistic":
            check(np.allclose(numeric.named_steps["scale"].mean_, imputer.transform(train).mean(axis=0)),
                  "Training-only scaling: " + feature_set)
        model = {"logistic": "logistic_regression", "tree": "decision_tree"}[kind]
        stored = pred.loc[pred.model.eq(model) & pred.feature_set.eq(feature_set)]
        selected = frame.set_index("event_id").loc[stored.event_id, columns]
        score = pipeline.predict_proba(selected)[:, 1]
        check(np.allclose(score, stored.y_score, rtol=0, atol=1e-12),
              "All saved fitted-model scores: " + feature_set)
        checked_predictions += len(stored)
    return {
        "status": "passed", "checks": checks, "event_contract": validation,
        "metric_rows_recomputed": len(metrics),
        "fitted_prediction_rows_recomputed": checked_predictions,
        "calendar_changed_rows_by_feature": calendar_changes,
        "note": "Read-only review of existing exploratory results; no retraining or scientific approval. "
                "This does not resolve the proposal's recovery-start vs confirmation target mismatch.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite review evidence: {args.output}")
    result = review(args.run, args.prepared)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
