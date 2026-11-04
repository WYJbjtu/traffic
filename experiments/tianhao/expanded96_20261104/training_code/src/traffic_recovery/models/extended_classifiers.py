"""Exploratory 30-minute L1 logistic and temporally calibrated RBF SVM.

Uses the existing event contract, feature resolver, and prediction schema. It does
not extend or change the team's logistic/tree/RF/HGB dispatch. Calibration is a
chronological holdout inside train; outcome maturity is mandatory audit metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import itertools
import json
import math
from pathlib import Path
from typing import Any
import warnings

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from traffic_recovery.models.contract import ExperimentContract, validate_event_table
from traffic_recovery.models.supervised import resolve_features

Estimator = Pipeline | CalibratedClassifierCV
SPLITS = ("train", "validation", "test")


@dataclass(frozen=True)
class ExtendedRules:
    """Frozen candidate grid and chronological calibration policy (HKT)."""

    version: str
    seed: int
    threshold: float
    calibration_start: pd.Timestamp
    minimum_purge_minutes: int
    l1: dict[str, Any]
    svm: dict[str, Any]

    @classmethod
    def from_path(cls, path: Path) -> ExtendedRules:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["selection_metric"] != "validation_log_loss" or payload["refit_after_selection"]:
            raise ValueError("Require validation_log_loss selection and no refit")
        rules = cls(str(payload["version"]), int(payload["seed"]),
                    float(payload["decision_threshold"]), pd.Timestamp(payload["calibration_start"]),
                    int(payload["minimum_purge_minutes"]), dict(payload["logistic_l1"]),
                    dict(payload["svm_rbf"]))
        rules.validate()
        return rules

    def validate(self) -> None:
        if not self.version or not 0 < self.threshold < 1:
            raise ValueError("Require a version and a threshold strictly between 0 and 1")
        if self.calibration_start.tzinfo is None or str(self.calibration_start.tz) not in {
            "Asia/Hong_Kong", "Hongkong", "UTC+08:00"}:
            raise ValueError("calibration_start must be an aware Hong Kong timestamp")
        if self.minimum_purge_minutes < 60:
            raise ValueError("Purge must protect at least the full 60-minute outcome window")
        for grid in (self.l1, self.svm):
            if not grid["C"] or not grid["class_weight"]:
                raise ValueError("Candidate grids must be nonempty")
            if any(not math.isfinite(float(c)) or float(c) <= 0 for c in grid["C"]):
                raise ValueError("C must be finite and positive")
            if any(weight not in (None, "balanced") for weight in grid["class_weight"]):
                raise ValueError("Only None/balanced class weights are supported")
        if not self.svm["gamma"] or any(
            g != "scale" and (not isinstance(g, (int, float)) or not math.isfinite(g) or g <= 0)
            for g in self.svm["gamma"]
        ):
            raise ValueError("gamma must be scale or finite and positive")
        if int(self.l1["max_iter"]) <= 0 or float(self.svm["cache_size_mb"]) <= 0:
            raise ValueError("Iteration and cache limits must be positive")

    def candidates(self, kind: str) -> list[dict[str, object]]:
        if kind == "logistic_l1":
            return [dict(C=c, class_weight=w) for c, w in
                    itertools.product(self.l1["C"], self.l1["class_weight"])]
        if kind == "svm_rbf":
            return [dict(C=c, gamma=g, class_weight=w) for c, g, w in
                    itertools.product(self.svm["C"], self.svm["gamma"], self.svm["class_weight"])]
        raise ValueError(f"Unknown extended model: {kind}")


@dataclass
class ExtendedResult:
    predictions: pd.DataFrame
    tuning: pd.DataFrame
    interpretation: pd.DataFrame
    summaries: list[dict[str, object]]
    fitted: dict[int, Estimator]
    calibration_audit: pd.DataFrame


def attach_outcome_maturity(dataset: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Attach outcome-only metadata, checking exact IDs, times, labels and splits.

    Never joins by row position. Input bytes/provenance must be supplied and
    recorded by the caller; matching schema alone does not authenticate a source.
    """
    required = {"event_id", "prediction_time", "label_30m", "outcome_maturity_at"}
    missing = required - set(events)
    if missing:
        raise ValueError(f"Event audit is missing columns: {sorted(missing)}")
    if not events.event_id.is_unique or not dataset.event_id.is_unique:
        raise ValueError("Dataset and audit require unique event IDs")
    if set(events.event_id) != set(dataset.event_id):
        raise ValueError("Audit IDs must exactly match dataset IDs")
    audit = events.set_index("event_id").loc[dataset.event_id].reset_index()
    for name in ("prediction_time", "label_30m"):
        left, right = dataset[name].reset_index(drop=True), audit[name].reset_index(drop=True)
        if not (left.eq(right) | (left.isna() & right.isna())).fillna(False).all():
            raise ValueError(f"Audit disagrees with dataset: {name}")
    split_column = "split" if "split" in audit else "split_proposal"
    if split_column not in audit or not np.array_equal(
        dataset.split.astype(str).to_numpy(), audit[split_column].astype(str).to_numpy()
    ):
        raise ValueError("Audit disagrees with dataset: split")
    result = dataset.copy()
    if "outcome_maturity_at" in result and not result.outcome_maturity_at.reset_index(drop=True).equals(
        audit.outcome_maturity_at.reset_index(drop=True)
    ):
        raise ValueError("Existing outcome maturity disagrees with event audit")
    result["outcome_maturity_at"] = audit.outcome_maturity_at.to_numpy()
    return result


def validate_outcome_maturity(frame: pd.DataFrame, contract: ExperimentContract, minimum_minutes: int = 60) -> None:
    """Reject incomplete outcome audit or windows crossing outer split boundaries."""
    if "outcome_maturity_at" not in frame or not isinstance(frame.outcome_maturity_at.dtype, pd.DatetimeTZDtype):
        raise ValueError("Require timezone-aware outcome_maturity_at audit metadata")
    maturity = frame.outcome_maturity_at
    for split, boundary in (("train", contract.validation_start), ("validation", contract.test_start)):
        mask = frame.split.eq(split)
        minimum = frame.loc[mask, "prediction_time"] + pd.Timedelta(minutes=minimum_minutes)
        if maturity.loc[mask].isna().any() or not maturity.loc[mask].ge(minimum).all():
            raise ValueError(f"{split} outcome maturity must cover the full purge horizon")
        if not maturity.loc[mask].lt(boundary).all():
            raise ValueError(f"{split} outcome window crosses the next split boundary")


def temporal_calibration_masks(
    frame: pd.DataFrame, contract: ExperimentContract, rules: ExtendedRules,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Split known train rows into fit/calibrate/purged; reject unsafe watermarks.

    Maturity must include the full outcome/follow-up window, not just the label's
    first recovery. Overlapping windows are purged before the calibration start.
    Both phases need two classes. No validation/test event can enter either phase.
    """
    rules.validate()
    if not rules.calibration_start < contract.validation_start:
        raise ValueError("Calibration must start before the outer validation period")
    if "outcome_maturity_at" not in frame:
        raise ValueError("SVM requires outcome_maturity_at audit metadata")
    maturity = frame.outcome_maturity_at
    if not isinstance(maturity.dtype, pd.DatetimeTZDtype):
        raise ValueError("Outcome maturity must be timezone-aware")
    train = frame.split.eq("train") & frame.label_30m.notna()
    minimum = frame.prediction_time + pd.Timedelta(minutes=rules.minimum_purge_minutes)
    if maturity.loc[train].isna().any() or not maturity.loc[train].ge(minimum.loc[train]).all():
        raise ValueError("Train outcome maturity must cover the full purge horizon")
    early = train & frame.prediction_time.lt(rules.calibration_start)
    fit = early & maturity.lt(rules.calibration_start)
    calibrate = train & frame.prediction_time.ge(rules.calibration_start)
    for name, mask in (("fit", fit), ("calibration", calibrate)):
        if frame.loc[mask, "label_30m"].nunique() != 2:
            raise ValueError(f"SVM {name} period needs both classes")
    audit = frame.loc[train, ["event_id", "prediction_time", "outcome_maturity_at"]].copy()
    audit["svm_role"] = np.select([fit.loc[train], calibrate.loc[train]],
                                 ["base_fit", "sigmoid_calibration"], default="purged")
    return fit, calibrate, audit


def base_pipeline(model: Estimator) -> Pipeline:
    """Return the fitted base pipeline, including a frozen SVM's preprocessing."""
    return model.estimator.estimator if isinstance(model, CalibratedClassifierCV) else model


def make_extended_pipeline(kind: str, features: tuple[str, ...], params: dict[str, object], rules: ExtendedRules) -> Pipeline:
    """Create an unfitted numeric Pipeline; fit/calibration policy lives in train_extended."""
    if kind not in {"logistic_l1", "svm_rbf"}:
        raise ValueError(f"Unknown extended model: {kind}")
    if kind == "logistic_l1":
        # 1.8+ uses l1_ratio; older supported sklearn versions still use penalty.
        regularization = {"l1_ratio": 1.0} if inspect.signature(LogisticRegression).parameters[
            "penalty"].default == "deprecated" else {"penalty": "l1"}
        classifier = LogisticRegression(**params, **regularization, solver="liblinear",
                                         max_iter=int(rules.l1["max_iter"]), random_state=rules.seed)
    else:
        # Default SVC has no internal probability CV (including sklearn 1.9).
        classifier = SVC(**params, kernel="rbf", cache_size=float(rules.svm["cache_size_mb"]),
                         random_state=rules.seed)
    preprocess = ColumnTransformer([("numeric", Pipeline([
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scale", StandardScaler()),
    ]), list(features))], remainder="drop")
    return Pipeline([("preprocess", preprocess), ("classifier", classifier)])


def train_extended(
    frame: pd.DataFrame, contract: ExperimentContract, rules: ExtendedRules,
    *, kind: str, feature_groups: tuple[str, ...],
) -> ExtendedResult:
    """Tune L1/SVM on validation log loss; return the team's prediction schema.

    Scope is explicitly one 30-minute horizon. Unknown labels remain excluded.
    All model/preprocessor fitting is confined to train; SVM fits preprocessing
    on the early train subset, then freezes it for late-train sigmoid calibration.
    RBF SVM has no linear coefficients; interpretation is an empty schema for it.
    Raises on invalid contracts, unavailable inputs, unsafe splits or nonconvergence.
    """
    rules.validate()
    if contract.horizons != (30,):
        raise ValueError("Extended experiment is frozen to the 30-minute horizon")
    validate_event_table(frame, contract)
    validate_outcome_maturity(frame, contract, rules.minimum_purge_minutes)
    features = resolve_features(frame, contract, feature_groups)
    if not frame.index.is_unique or any(not is_numeric_dtype(frame[c]) for c in features):
        raise ValueError("Require a unique row index and numeric features")
    if np.isinf(frame[list(features)].to_numpy(dtype=float, na_value=np.nan)).any():
        raise ValueError("Infinite feature values are invalid")
    masks = {split: frame.split.eq(split) & frame.label_30m.notna() for split in SPLITS}
    if any(not m.any() for m in masks.values()) or frame.loc[masks["train"], "label_30m"].nunique() != 2:
        raise ValueError("Require known labels in every split and two train classes")
    fit_mask, calibrate, audit = masks["train"], pd.Series(False, index=frame.index), pd.DataFrame()
    if kind == "svm_rbf":
        fit_mask, calibrate, audit = temporal_calibration_masks(frame, contract, rules)
    candidates = rules.candidates(kind)
    best_model, best_params, best_score, best_id = None, None, math.inf, -1
    tuning = []
    validation_y = frame.loc[masks["validation"], "label_30m"].astype(int)
    for candidate_id, params in enumerate(candidates):
        model = make_extended_pipeline(kind, features, params, rules)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(frame.loc[fit_mask, list(features)], frame.loc[fit_mask, "label_30m"].astype(int))
        if kind == "svm_rbf":
            # FrozenEstimator.fit is a no-op. One explicit prediction pass avoids
            # an unnecessary default 5-fold split (which also fails on tiny
            # calibration sets). Reusing these indices never refits the base.
            positions = np.arange(int(calibrate.sum()))
            model = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid", ensemble=False,
                                           cv=[(positions, positions)])
            model.fit(frame.loc[calibrate, list(features)], frame.loc[calibrate, "label_30m"].astype(int))
        score = float(log_loss(validation_y, model.predict_proba(frame.loc[masks["validation"], list(features)])[:, 1], labels=[0, 1]))
        if not math.isfinite(score):
            raise ValueError("Nonfinite validation loss")
        classifier = base_pipeline(model).named_steps["classifier"]
        nonzero = int(np.count_nonzero(classifier.coef_)) if kind == "logistic_l1" else math.nan
        tuning.append(dict(model_version=rules.version, model=kind, feature_set="+".join(feature_groups),
            horizon_min=30, candidate_id=candidate_id, parameters=json.dumps(params, sort_keys=True),
            validation_log_loss=score, validation_n=int(masks["validation"].sum()), selected=False,
            base_fit_n=int(fit_mask.sum()), calibration_n=int(calibrate.sum()),
            n_features=len(features), nonzero_coefficients=nonzero))
        if score < best_score:  # First candidate wins an exact tie.
            best_model, best_params, best_score, best_id = model, params, score, candidate_id
    tuning[best_id]["selected"] = True
    rows = []
    for split, mask in masks.items():
        part = frame.loc[mask, ["event_id", "prediction_time", "split"]].copy()
        part["horizon_min"] = 30
        part["model"], part["feature_set"] = kind, "+".join(feature_groups)
        part["y_true"] = frame.loc[mask, "label_30m"].astype(int)
        part["y_score"] = best_model.predict_proba(frame.loc[mask, list(features)])[:, 1]
        part["y_pred"] = part.y_score.ge(rules.threshold).astype(int)
        part["score_kind"], part["threshold"], part["model_version"] = "probability", rules.threshold, rules.version
        part["n_censored_in_split"] = int((frame.split.eq(split) & frame.label_30m.isna()).sum())
        part["n_missing_feature_in_split"] = int(frame.loc[frame.split.eq(split), list(features)].isna().any(axis=1).sum())
        rows.append(part)
    interpretation = []
    classifier = base_pipeline(best_model).named_steps["classifier"]
    if kind == "logistic_l1":
        for feature, value in zip(features, classifier.coef_[0]):
            interpretation.append(dict(model_version=rules.version, model=kind,
                feature_set="+".join(feature_groups), horizon_min=30, feature=feature,
                importance_type="coefficient", value=float(value), odds_ratio=math.exp(float(np.clip(value, -700, 700)))))
    summary = dict(horizon_min=30, parameters=best_params, validation_log_loss=best_score,
        base_fit_n=int(fit_mask.sum()), calibration_n=int(calibrate.sum()),
        train_rows=int(masks["train"].sum()), validation_rows=int(masks["validation"].sum()),
        test_rows=int(masks["test"].sum()), refit_after_selection=False,
        calibration_method="sigmoid" if kind == "svm_rbf" else None,
        calibration_start=rules.calibration_start.isoformat() if kind == "svm_rbf" else None)
    if kind == "svm_rbf":
        summary["support_vectors"] = int(classifier.n_support_.sum())
    columns = ["model_version", "model", "feature_set", "horizon_min", "feature", "importance_type", "value", "odds_ratio"]
    return ExtendedResult(pd.concat(rows, ignore_index=True), pd.DataFrame(tuning),
                          pd.DataFrame(interpretation, columns=columns), [summary], {30: best_model}, audit)
