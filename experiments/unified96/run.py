"""Authenticated P1 retrospective comparison; --context activates F0–F7.

Run from repo root: uv run --locked python -m experiments.unified96.run --out data/local/unified96/f0-f4-p1-v1
Output directory must not exist. Does not scan the 35m-row five-minute history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.metrics import log_loss, roc_auc_score, average_precision_score

from scripts.spatial96_inferred_v2 import S1, S2, S3, S4
from traffic_recovery.data.http import sha256_file
from traffic_recovery.models.expanded96 import LOCAL, HISTORY, candidate_models, metrics

ROOT = Path(__file__).resolve().parents[2]
EVENTS = "data/local/expanded96-release/prepared-v1/processed/events.parquet"
HISTORY_FILE = "data/local/expanded96-release/model-a0-a2-v2/history_features.parquet"
SPATIAL = "data/local/spatial96/inferred-v2/event_spatial_features.parquet"
LINEAGE = "data/local/spatial96/inferred-v2/event_neighbor_lineage.parquet"
Q = ["valid_slots", "history_observed_bins"]  # observation counts, NOT vehicle flow
L = [x for x in LOCAL if x != "valid_slots"]
H = [x for x in HISTORY if x != "history_observed_bins"]
S = S1 + S2 + S3 + S4
from experiments.unified96.context import C, W

ARMS = {f"F{i}": L + H + Q + (C if i % 4 in (1, 3) else [])
        + (W if i % 4 in (2, 3) else []) + (S if i >= 4 else []) for i in range(8)}
MODELS = ("logistic_regression", "random_forest", "xgboost", "hist_gradient_boosting")
SPLITS = ("train", "validation", "test")


def event_hash(ids: pd.Series) -> str:
    """Stable SHA-256 of sorted unique newline-delimited event IDs."""
    if ids.isna().any() or ids.duplicated().any():
        raise ValueError("Missing or duplicate event IDs")
    return hashlib.sha256("\n".join(sorted(ids.astype(str))).encode("utf-8")).hexdigest()


def require_available(frame: pd.DataFrame, column: str, *, optional: bool = False) -> None:
    """Reject future/naive timestamps; nullable optional watermarks remain missing."""
    if not optional and frame[column].isna().any():
        raise ValueError(f"Missing required availability: {column}")
    for name in (column, "prediction_time"):
        if not isinstance(frame[name].dtype, pd.DatetimeTZDtype):
            raise ValueError(f"Timezone-aware timestamps required: {name}")
    if (frame[column].dropna().dt.tz_convert("UTC") > frame.loc[frame[column].notna(), "prediction_time"].dt.tz_convert("UTC")).any():
        raise ValueError(f"Future observation leaked: {column}")


def merge_verified(events: pd.DataFrame, history: pd.DataFrame, spatial: pd.DataFrame,
                   lineage: pd.DataFrame, population: str) -> pd.DataFrame:
    """Join authentic event-level inputs; reject identity, split and as-of violations.

    Spatial source has one row per event per population. Lineage can have multiple
    real neighbours per event; it is checked separately against the event clock.
    All datetimes are timezone-aware HKT; speed missingness is preserved as NA.
    """
    if population not in ("INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED"):
        raise ValueError("P3 not approved for model training")
    selected = spatial.loc[spatial.population.eq(population)].drop(columns="population")
    for name, frame, keys in (("events", events, ["event_id"]), ("history", history, ["event_id"]),
                              ("spatial", selected, ["event_id", "prediction_time"])):
        if frame.duplicated(keys).any() or frame.event_id.isna().any():
            raise ValueError(f"Duplicate/missing {name} identity")
    for name, frame in (("events", events), ("spatial", selected)):
        if not isinstance(frame.prediction_time.dtype, pd.DatetimeTZDtype):
            raise ValueError(f"Timezone-aware prediction_time required in {name}")
    if events.split_proposal.isna().any() or not set(events.split_proposal).issubset(SPLITS):
        raise ValueError("Unknown or missing temporal split")
    if set(events.definition_version) != {"lane-observed-confirmation-v1"}:
        raise ValueError("Different target definition")
    if not set(history.event_id) == set(events.event_id):
        raise ValueError("History does not cover exactly the event IDs")
    if len(selected) != len(events) or set(selected.event_id) != set(events.event_id):
        raise ValueError("Spatial cohort identity differs from release")
    joined = events.merge(history, on="event_id", validate="one_to_one").merge(
        selected, on=["event_id", "prediction_time"], validate="one_to_one")
    if len(joined) != len(events):
        raise ValueError("Event/time join lost records")
    for col, optional in (("feature_max_available_at", False), ("history_latest_available_at", True)):
        require_available(joined, col, optional=optional)
    if joined.reference_fit_end.isna().any() or (joined.reference_fit_end >= joined.prediction_time).any():
        raise ValueError("Reference fit overlaps event")
    lines = lineage.loc[lineage.population.eq(population)]
    if not set(lines.event_id).issubset(set(events.event_id)):
        raise ValueError("Unknown neighbor event identity")
    if lines.duplicated(["event_id", "neighbor_detector", "neighbor_direction", "neighbor_lane", "side"]).any():
        raise ValueError("Duplicate neighbor/side identity")
    matched = lines.merge(events[["event_id", "prediction_time", "detector_id", "direction", "lane_id"]],
                          on="event_id", validate="many_to_one")
    if not matched[["target_detector", "target_direction", "target_lane"]].reset_index(drop=True).set_axis(
            ["detector_id", "direction", "lane_id"], axis=1).equals(
            matched[["detector_id", "direction", "lane_id"]].reset_index(drop=True)):
        raise ValueError("Neighbor target unit mismatch")
    for col in ("observed_at", "available_at", "last_source_available_at"):
        require_available(matched, col)
    counts = lines.groupby("event_id").size()
    actual = joined.event_id.map(counts).fillna(0).astype(int)
    if not actual.eq(joined.observed_neighbor_count).all():
        raise ValueError("Spatial observation counts do not agree with lineage")
    return joined.loc[joined.label_30m.notna() & joined.observed_neighbor_count.gt(0)].copy()


def load(root: Path = ROOT, population: str = "INFERRED_EXPLORATORY") -> tuple[pd.DataFrame, dict[str, str]]:
    """Verify published source hashes, then load projected event-level files only."""
    model_manifest = json.loads((root / "data/local/expanded96-release/model-a0-a2-v2/manifest.json").read_text(encoding="utf-8"))
    spatial_manifest = json.loads((root / "reports/spatial96_inferred_v2/output_sha256.json").read_text(encoding="utf-8"))
    expected = {EVENTS: model_manifest["source_sha256"]["events"],
                HISTORY_FILE: model_manifest["outputs_sha256"]["history_features.parquet"],
                SPATIAL: spatial_manifest[SPATIAL], LINEAGE: spatial_manifest[LINEAGE]}
    if model_manifest["target"] != "recovery_confirmation_v1":
        raise ValueError("Frozen target mismatch")
    for name, digest in expected.items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"Input SHA-256 mismatch: {name}")
    events = pd.read_parquet(root / EVENTS, columns=["event_id", "detector_id", "direction", "lane_id",
        "prediction_time", "split_proposal", "definition_version", "label_30m", "reference_fit_end",
        "feature_max_available_at", *LOCAL])
    history = pd.read_parquet(root / HISTORY_FILE)
    spatial = pd.read_parquet(root / SPATIAL)
    lineage = pd.read_parquet(root / LINEAGE, columns=["event_id", "population", "target_detector",
        "target_direction", "target_lane", "neighbor_detector", "neighbor_direction", "neighbor_lane", "side",
        "observed_at", "available_at", "last_source_available_at"])
    frame = merge_verified(events, history, spatial, lineage, population)
    frame = frame.rename(columns={"split_proposal": "split", "label_30m": "label"})
    frame["target_version"] = "recovery_confirmation_v1"
    frame["horizon_min"] = 30
    frame["population"] = population
    for split in SPLITS:
        subset = frame.loc[frame.split.eq(split)]
        if set(subset.label.astype(int)) != {0, 1}:
            raise ValueError(f"Both label classes required in {split}")
        event_hash(subset.event_id)
    return frame, expected


def paired_bootstrap(left: pd.DataFrame, right: pd.DataFrame, *, replicates: int = 1000,
                     seed: int = 42) -> dict[str, object]:
    """Detector-cluster paired ROC/PR intervals; identical draws for both arms."""
    keys = ["event_id", "detector_id", "y_true"]
    if left.duplicated("event_id").any() or right.duplicated("event_id").any():
        raise ValueError("Duplicate paired prediction identity")
    merged = left[keys + ["y_score"]].merge(right[keys + ["y_score"]], on=keys,
        how="outer", validate="one_to_one", indicator=True, suffixes=("_left", "_right"))
    if len(merged) != len(left) or len(merged) != len(right) or not merged._merge.eq("both").all():
        raise ValueError("Unpaired event ID, detector or target")
    if replicates < 1:
        raise ValueError("At least one resample required")
    clusters = sorted(merged.detector_id.unique())
    if len(clusters) < 2:
        raise ValueError("Detector bootstrap requires at least two clusters")
    positions = [np.flatnonzero(merged.detector_id.to_numpy() == d) for d in clusters]
    y = merged.y_true.to_numpy(dtype=int)
    a = merged.y_score_left.to_numpy(dtype=float); b = merged.y_score_right.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    out: dict[str, object] = {"clusters": len(clusters), "events": len(merged), "replicates_requested": replicates,
                              "seed": seed, "event_ids_sha256": event_hash(merged.event_id)}
    draws: dict[str, list[float]] = {"roc_auc": [], "average_precision": []}
    invalid = 0
    for _ in range(replicates):
        sample = np.concatenate([positions[i] for i in rng.integers(0, len(clusters), len(clusters))])
        if len(np.unique(y[sample])) != 2:
            invalid += 1
            continue
        draws["roc_auc"].append(float(roc_auc_score(y[sample], b[sample]) - roc_auc_score(y[sample], a[sample])))
        draws["average_precision"].append(float(average_precision_score(y[sample], b[sample]) - average_precision_score(y[sample], a[sample])))
    out["invalid_single_class"] = invalid
    for name, fn in (("roc_auc", roc_auc_score), ("average_precision", average_precision_score)):
        out[name] = {"observed_delta": float(fn(y, b) - fn(y, a)), "valid_resamples": len(draws[name]),
                     "ci_95_percentile": [float(v) for v in np.quantile(draws[name], [.025, .975])] if draws[name] else None}
    return out


def run(output: Path, *, root: Path = ROOT) -> None:
    """Run eight exploratory F0/F4 arms without touching published runs."""
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")
    data, inputs = load(root)
    output.mkdir(parents=True)
    from time import perf_counter
    started = perf_counter()
    predictions, rows, selections = [], [], []
    for arm, columns in ((name, ARMS[name]) for name in ('F0', 'F4')):
        train, validation, test = (data.loc[data.split.eq(s)] for s in SPLITS)
        for model_name in MODELS:
            contenders = candidate_models()[model_name]
            losses = []
            for candidate, model in enumerate(contenders):
                model.fit(train[columns].to_numpy(dtype=float), train.label.to_numpy(dtype=int))
                p = model.predict_proba(validation[columns].to_numpy(dtype=float))[:, 1]
                losses.append(float(log_loss(validation.label.to_numpy(dtype=int), np.clip(p, 1e-7, 1-1e-7))))
            choice = int(np.argmin(losses)); selected = contenders[choice]
            selections.append({"arm": arm, "model": model_name, "selected_candidate": choice,
                               "validation_log_loss": losses[choice], "candidate_log_losses": losses})
            for split, frame in (("validation", validation), ("test", test)):
                y = frame.label.to_numpy(dtype=int)
                p = selected.predict_proba(frame[columns].to_numpy(dtype=float))[:, 1]
                pred = (p >= 0.5).astype(int)  # predeclared threshold, no test tuning
                rows.append({"population": "INFERRED_EXPLORATORY", "arm": arm, "model": model_name,
                    "split": split, "target_version": "recovery_confirmation_v1", "horizon_min": 30,
                    "n_events": len(frame), "n_positive": int(y.sum()), "n_negative": int(len(y)-y.sum()),
                    "event_ids_sha256": event_hash(frame.event_id), "selected_candidate": choice,
                    "threshold": 0.5, **metrics(y, p, pred)})
                predictions.append(pd.DataFrame({"event_id": frame.event_id.to_numpy(),
                    "detector_id": frame.detector_id.to_numpy(), "prediction_time": frame.prediction_time.to_numpy(),
                    "split": split, "target_version": "recovery_confirmation_v1", "horizon_min": 30,
                    "population": "INFERRED_EXPLORATORY", "model": model_name, "feature_arm": arm,
                    "y_true": y, "y_score": p, "y_pred": pred, "selected_threshold": 0.5,
                    "experiment_id": "unified96-p1-f0-f4-v1"}))
    results = pd.DataFrame(rows); saved = pd.concat(predictions, ignore_index=True)
    results.to_csv(output / "metrics.csv", index=False)
    saved.to_parquet(output / "predictions.parquet", index=False)
    gains = []
    for model in MODELS:
        subset = saved.loc[saved.model.eq(model) & saved.split.eq("test")]
        left = subset.loc[subset.feature_arm.eq("F0")]
        right = subset.loc[subset.feature_arm.eq("F4")]
        gains.append({"model": model, **paired_bootstrap(left, right)})
    (output / "paired_bootstrap.json").write_text(json.dumps(gains, indent=2) + "\n", encoding="utf-8")
    (output / "validation_selection.json").write_text(json.dumps(selections, indent=2) + "\n", encoding="utf-8")
    manifest = {"status": "RETROSPECTIVE_EXPLORATORY_NOT_BLIND", "experiment_id": "unified96-p1-f0-f4-v1",
        "target": "recovery_confirmation_v1", "population": "INFERRED_EXPLORATORY", "horizon_min": 30,
        "inputs_sha256": inputs, "split_event_ids_sha256": {s: event_hash(data.loc[data.split.eq(s), "event_id"]) for s in SPLITS},
        "split_counts": {s: int(data.split.eq(s).sum()) for s in SPLITS},
        "feature_groups": {"L": L, "H": H, "Q": Q, "S": S}, "arms": {k: ARMS[k] for k in ('F0', 'F4')}, "excluded_groups": {
        "C": "verified official holiday event feature input unavailable locally",
        "W": "authenticated King's Park weather event/station input unavailable locally"},
        "selection": "two frozen candidates/model, minimum validation log loss, no refit; fixed threshold 0.5",
        "seed": 42, "git_start_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "runtime_seconds": perf_counter() - started,
        "software": {"python": platform.python_version(), "pandas": pd.__version__, "sklearn": sklearn.__version__, "xgboost": xgboost.__version__},
        "outputs_sha256": {name: sha256_file(output / name) for name in ("metrics.csv", "predictions.parquet", "paired_bootstrap.json", "validation_selection.json")}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New output directory (must not exist)")
    parser.add_argument('--context', type=Path, help='Authenticated calendar_weather96 bundle; activates new matrix runner')
    parser.add_argument('--arms', nargs='+', choices=list(ARMS), default=['F3', 'F7', 'F0', 'F4', 'F1', 'F5', 'F2', 'F6'])
    args = parser.parse_args()
    if args.context is None:
        run(args.out)  # original F0/F4 reproduction; frozen outputs never overwritten
    else:
        from experiments.unified96.matrix import run_matrix
        run_matrix(args.out, args.context, args.arms)


if __name__ == "__main__":
    main()
