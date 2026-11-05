"""Read-only adapters for saved exploratory research artifacts (no model fitting)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

MODELS = ("logistic_regression", "decision_tree", "random_forest", "hist_gradient_boosting")
METRICS = ("roc_auc", "pr_auc", "f1", "macro_f1", "balanced_accuracy")


def load_artifacts(root: Path, experiment: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return test metrics, test predictions and metadata for one named saved run.

    Missing files/columns fail explicitly; experiments are never concatenated.
    Tianhao metrics are wide and 30m-only; Member4 metrics are long and 15/30/60m.
    """
    if experiment not in ("member4", "tianhao"):
        raise ValueError(f"Unknown experiment: {experiment}")
    folder = root / ("experiments/member4/comparison-hf-v1" if experiment == "member4" else "experiments/tianhao/rerun_20261101")
    predictions = pd.read_parquet(folder / "predictions.parquet")
    required = {"event_id", "prediction_time", "split", "model", "feature_set", "horizon_min", "y_true", "y_pred", "y_score"}
    if required - set(predictions):
        raise ValueError(f"{folder}: prediction columns missing: {sorted(required - set(predictions))}")
    predictions = predictions.loc[predictions.split.eq("test")].copy()
    if experiment == "member4":
        raw = pd.read_csv(folder / "metrics.csv")
        needed = {"split", "model", "feature_set", "horizon_min", "metric_name", "metric_value"}
        if needed - set(raw):
            raise ValueError(f"{folder}: metric columns missing: {sorted(needed - set(raw))}")
        metrics = raw.loc[raw.split.eq("test") & raw.model.isin(MODELS) & raw.metric_name.isin(METRICS)].copy()
        metadata = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    else:
        raw = pd.read_csv(folder / "metrics_summary.csv")
        needed = {"split", "model", "feature_set", *METRICS}
        if needed - set(raw):
            raise ValueError(f"{folder}: metric columns missing: {sorted(needed - set(raw))}")
        metrics = raw.loc[raw.split.eq("test") & raw.model.isin(MODELS)].melt(
            id_vars=["model", "feature_set", "split"], value_vars=list(METRICS),
            var_name="metric_name", value_name="metric_value",
        )
        metrics["horizon_min"] = 30
        metadata = json.loads((root / "experiments/member4/model-dataset-manifest-hf.json").read_text(encoding="utf-8"))
    if metrics.empty or predictions.empty:
        raise ValueError(f"{folder}: no saved test results")
    keys = ["event_id", "model", "feature_set", "horizon_min", "split"]
    if predictions.duplicated(keys).any():
        raise ValueError(f"{folder}: duplicate out-of-sample prediction keys")
    return metrics, predictions, pd.DataFrame([{"experiment": experiment, "events": metadata.get("dataset_manifest", {}).get("validation", metadata.get("validation", {})).get("events"), "approval": metadata.get("scientific_approval", "pending_team_review")}])


def select_predictions(predictions: pd.DataFrame, *, model: str, feature_set: str, horizon: int) -> pd.DataFrame:
    """Select a single test arm; never substitute an outcome for a prediction."""
    return predictions.loc[
        predictions.split.eq("test") & predictions.model.eq(model)
        & predictions.feature_set.eq(feature_set) & predictions.horizon_min.eq(horizon)
    ].copy()


def confusion_counts(arm: pd.DataFrame) -> list[list[int]]:
    """Observed rows, predicted columns; exclude unknown outcomes, never coerce to zero."""
    known = arm.loc[arm.y_true.notna() & arm.y_pred.notna()]
    return [[int(((known.y_true == y) & (known.y_pred == p)).sum()) for p in (0, 1)] for y in (0, 1)]


def aware_hkt(values: pd.Series) -> pd.Series:
    """Convert an aware timestamp series to HKT; naive local timestamps are invalid."""
    parsed = pd.to_datetime(values, errors="raise")
    if not isinstance(parsed.dtype, pd.DatetimeTZDtype):
        raise ValueError("prediction_time must contain timezone-aware timestamps")
    return parsed.dt.tz_convert("Asia/Hong_Kong")


def join_event_metadata(predictions: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Join matching long-window events by ID AND aware instant; reject wrong cohorts.

    A test prediction may be missing from an incomplete local export, but a zero
    overlap is an error rather than evidence that the detector is unknown.
    """
    required = {"event_id", "prediction_time", "detector_id", "direction", "lane_id"}
    if required - set(events) or events.event_id.duplicated().any():
        raise ValueError("events must have unique event_id, prediction_time, detector_id, direction, lane_id")
    source = events.copy()
    source["prediction_time"] = aware_hkt(source.prediction_time)
    sample = predictions.copy()
    sample["prediction_time"] = aware_hkt(sample.prediction_time)
    joined = sample.merge(source, on=["event_id", "prediction_time"], how="left", validate="one_to_one", suffixes=("", "_event"))
    if joined.detector_id.notna().sum() == 0:
        raise ValueError("no matching event/time keys: check that the data are from the long-window cohort")
    return joined


def event_history(bins_path: Path, event: pd.Series, *, lookback_minutes: int = 90) -> pd.DataFrame:
    """Load authentic same-lane bins ending by prediction time from a local Parquet file/directory.

    Only bins whose end AND archive replay availability precede prediction are
    returned. Missing columns raise; empty means no compatible observed history.
    """
    needed = {"detector_id", "direction", "lane_id", "timestamp", "available_at", "speed_kmh"}
    frame = pd.read_parquet(bins_path, filters=[("detector_id", "==", str(event.detector_id))])
    if needed - set(frame):
        raise ValueError(f"bins missing: {sorted(needed - set(frame))}")
    end = pd.Timestamp(event.prediction_time)
    if end.tzinfo is None:
        raise ValueError("prediction_time must be timezone-aware")
    times = aware_hkt(frame.timestamp)
    available = aware_hkt(frame.available_at)
    mask = (frame.detector_id.astype(str).eq(str(event.detector_id)) & frame.direction.eq(event.direction)
            & frame.lane_id.eq(event.lane_id) & times.le(end) & available.le(end)
            & times.ge(end - pd.Timedelta(minutes=lookback_minutes)))
    result = frame.loc[mask, ["timestamp", "speed_kmh"]].copy()
    result["timestamp"] = times.loc[mask]
    return result.sort_values("timestamp")


def temporal_summary(events: pd.DataFrame, horizon: int = 30) -> pd.DataFrame:
    """Descriptive counts across ALL events, including unknown labels; HKT clock only.

    Does not infer holiday status from dates. Requires the original event table.
    """
    label = f"label_{horizon}m"
    if not {"event_id", "prediction_time", label} <= set(events):
        raise ValueError(f"event table must contain event_id, prediction_time, {label}")
    if events.event_id.duplicated().any():
        raise ValueError("event_id must be unique")
    time = aware_hkt(events.prediction_time)
    hour = time.dt.hour
    period = pd.cut(hour, [-1, 5, 9, 16, 20, 23], labels=["overnight", "morning peak", "daytime", "evening peak", "late night"])
    frame = pd.DataFrame({"period": period, "week": time.dt.dayofweek.map(lambda x: "weekend" if x >= 5 else "weekday"),
                          "month": time.dt.strftime("%Y-%m"), "known": events[label].notna(),
                          "positive": events[label].eq(1).fillna(False)})
    return frame.groupby(["month", "week", "period"], observed=True).agg(
        events=("known", "size"), known=("known", "sum"), recovered=("positive", "sum")
    ).reset_index().assign(
        missing_rate=lambda d: 1 - d.known / d.events,
        known_recovery_rate=lambda d: d.recovered / d.known.replace(0, float("nan")),
    )
