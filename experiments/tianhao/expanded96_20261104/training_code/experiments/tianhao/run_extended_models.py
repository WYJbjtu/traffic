"""Portable CLI for the notebook's L1/SVM extension and unchanged reference arms."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import subprocess
from uuid import uuid4
from pathlib import Path
import platform
import shutil
import sys
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from traffic_recovery.models.benchmarks import BenchmarkRules, benchmark_predictions
from traffic_recovery.models.contract import ExperimentContract, validate_event_table
from traffic_recovery.models.evaluation import evaluate_predictions
from traffic_recovery.models.extended_classifiers import ExtendedRules, attach_outcome_maturity, train_extended, validate_outcome_maturity
from traffic_recovery.models.supervised import SupervisedRules, train_supervised
from traffic_recovery.models.provenance import start_run
from traffic_recovery.models.experiment_diagnostics import feature_gains, error_diagnostics
from run_experiment import add_trend

LOGGER = logging.getLogger(__name__)
STATUS = "EXPLORATORY — NOT APPROVED AS FINAL RESULTS"
MODELS = ("logistic_regression", "decision_tree", "logistic_l1", "svm_rbf")
KEYS = ["model", "feature_set", "horizon_min", "split", "event_id"]


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def repository_state() -> dict[str, object]:
    """Read Git evidence for this repo, independent of the caller's directory.

    GIT_BINARY is optional for hosts whose system git launcher is unavailable.
    A missing Git executable is an explicit provenance failure, not a clean state.
    """
    executable = os.environ.get("GIT_BINARY", "git")
    try:
        commit = subprocess.run([executable, "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        dirty = bool(subprocess.run([executable, "-C", str(ROOT), "status", "--porcelain"],
            check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip())
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Git provenance unavailable; install Git or set GIT_BINARY") from error
    return {"commit": commit, "dirty": dirty}


def summarise_predictions(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Use shared metric definitions and retain each arm's cohort/counts."""
    metrics = evaluate_predictions(predictions, version_column="experiment_version")
    index = ["model", "feature_set", "horizon_min", "split"]
    wide = metrics.pivot_table(index=index, columns="metric_name", values="metric_value").reset_index()
    counts = []
    for key, part in predictions.groupby(index, sort=False):
        tn, fp, fn, tp = confusion_matrix(part.y_true, part.y_pred, labels=[0, 1]).ravel()
        counts.append(dict(zip(index, key), n=len(part), tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp)))
    confusion = pd.DataFrame(counts)
    wide = wide.merge(confusion[[*index, "n"]], on=index, validate="one_to_one")
    validation = wide.loc[wide.split.eq("validation") & wide.model.isin(MODELS)].copy()
    validation["n_groups"] = validation.feature_set.str.count(r"\+") + 1
    selected = validation.sort_values(["log_loss", "n_groups", "model", "feature_set"], kind="stable")
    selected = selected.groupby("model", sort=False).head(1).reset_index(drop=True)
    selected["is_overall_choice"] = selected.index == 0
    return metrics, wide, confusion, selected


def compare_reference(predictions: pd.DataFrame, reference_path: Path) -> dict[str, object]:
    """Compare all 24 arms only after fitting/selection, never for retuning."""
    reference = pd.read_parquet(reference_path)
    if predictions.duplicated(KEYS).any() or reference.duplicated(KEYS).any():
        raise ValueError("Reference comparison requires unique experiment/event keys")
    paired = predictions.merge(reference, on=KEYS, how="outer", suffixes=("_new", "_reference"),
                               validate="one_to_one", indicator=True)
    if not paired._merge.eq("both").all():
        raise ValueError("Reference prediction cohort/arms differ")
    for col in ("prediction_time", "y_true", "y_pred", "score_kind"):
        if not paired[col + "_new"].eq(paired[col + "_reference"]).all():
            raise ValueError(f"Reference mismatch: {col}")
    delta = float((paired.y_score_new - paired.y_score_reference).abs().max())
    if not np.allclose(paired.y_score_new, paired.y_score_reference, rtol=0, atol=1e-12):
        raise ValueError(f"Reference probability mismatch (max difference {delta})")
    return {"status": "passed", "rows": len(paired), "max_score_difference": delta,
            "reference_sha256": sha(reference_path)}


def plot_results(predictions: pd.DataFrame, summary: pd.DataFrame, selected: pd.DataFrame,
                 interpretation: pd.DataFrame, output: Path) -> None:
    """Save real ROC/PR, four confusion matrices and selected linear coefficients."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve, precision_recall_curve, roc_auc_score, average_precision_score

    output.mkdir()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for row in selected.itertuples():
        part = predictions.loc[predictions.model.eq(row.model) & predictions.feature_set.eq(row.feature_set)
                               & predictions.split.eq("test")]
        fpr, tpr, _ = roc_curve(part.y_true, part.y_score)
        precision, recall, _ = precision_recall_curve(part.y_true, part.y_score)
        axes[0].plot(fpr, tpr, label=f"{row.model}: {roc_auc_score(part.y_true, part.y_score):.3f}")
        axes[1].plot(recall, precision, label=f"{row.model}: {average_precision_score(part.y_true, part.y_score):.3f}")
    axes[0].plot([0, 1], [0, 1], "--", color="grey")
    prevalence = predictions.loc[predictions.split.eq("test")].y_true.mean()
    axes[1].axhline(prevalence, ls="--", color="grey")
    axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="Test ROC")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Test PR (AP)")
    for ax in axes:
        ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(output / "roc_pr.png", dpi=150); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(9, 8))
    for ax, row in zip(axes.flat, selected.itertuples()):
        part = predictions.loc[predictions.model.eq(row.model) & predictions.feature_set.eq(row.feature_set)
                               & predictions.split.eq("test")]
        cm = confusion_matrix(part.y_true, part.y_pred, labels=[0, 1])
        ax.imshow(cm, cmap="Blues")
        for (i, j), value in np.ndenumerate(cm):
            ax.text(j, i, str(value), ha="center", va="center", color="white" if value > cm.max() * .6 else "black")
        ax.set(title=f"{row.model} / n={len(part)}", xlabel="Predicted", ylabel="Actual",
               xticks=[0, 1], yticks=[0, 1])
    fig.tight_layout(); fig.savefig(output / "confusion_matrices.png", dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    for ax, model in zip(axes, ("logistic_regression", "logistic_l1")):
        feature_set = selected.loc[selected.model.eq(model), "feature_set"].iloc[0]
        coefficients = interpretation.loc[interpretation.model.eq(model) & interpretation.feature_set.eq(feature_set)]
        coefficients = coefficients.sort_values("value")
        ax.barh(coefficients.feature.str.removeprefix("numeric__"), coefficients.value)
        ax.set(title=model, xlabel="Standardized coefficient")
    fig.tight_layout(); fig.savefig(output / "linear_coefficients.png", dpi=150); plt.close(fig)


def run(*, dataset_path: Path, events_path: Path, contract_path: Path, rules_path: Path,
        supervised_rules_path: Path, benchmark_rules_path: Path, output: Path,
        reference_path: Path | None = None, figures: bool = False) -> dict[str, object]:
    """Fit all original/new arms into a fresh directory, preserving source artifacts."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {output}")
    started_at, started = start_run()
    git_state = repository_state()
    lock_hash = sha(ROOT / "uv.lock")
    run_id = f"{started_at:%Y%m%dT%H%M%S.%fZ}-{uuid4().hex[:12]}"
    inputs = dict(dataset=dataset_path, events=events_path, contract=contract_path,
                  extended_rules=rules_path, supervised_rules=supervised_rules_path,
                  benchmark_rules=benchmark_rules_path)
    inputs_record = {key: {"file": path.name, "sha256": sha(path)} for key, path in inputs.items()}
    frame = attach_outcome_maturity(pd.read_parquet(dataset_path), pd.read_parquet(events_path))
    contract = ExperimentContract.from_path(contract_path)
    validation = validate_event_table(frame, contract)
    rules = ExtendedRules.from_path(rules_path)
    validate_outcome_maturity(frame, contract, rules.minimum_purge_minutes)
    supervised = SupervisedRules.from_path(supervised_rules_path)
    benchmark = BenchmarkRules.from_path(benchmark_rules_path)
    if contract.horizons != (30,) or rules.seed != supervised.seed or rules.threshold != supervised.decision_threshold:
        raise ValueError("Require a 30-minute contract and matching seeds/decision thresholds")
    if benchmark.decision_threshold != rules.threshold:
        raise ValueError("Benchmark and model classification thresholds must agree")
    feature_sets = [tuple(list(contract.feature_groups)[:i]) for i in range(1, len(contract.feature_groups) + 1)]
    if not feature_sets:
        raise ValueError("Require at least one feature group")
    output.mkdir(parents=True, exist_ok=False)
    config_dir = output / "configs"; config_dir.mkdir()
    for name in ("contract", "extended_rules", "supervised_rules", "benchmark_rules"):
        shutil.copy2(inputs[name], config_dir / (name + ".json"))
    plan = dict(status=STATUS, version=rules.version, prior_test_exposure=True,
        target="30-minute observed recovery confirmation; not recovery start", seed=rules.seed,
        selection="validation_log_loss; trend rule validation_macro_f1", threshold=rules.threshold,
        refit_after_selection=False, feature_sets=feature_sets, model_kinds=list(MODELS), input_hashes=inputs_record,
        calibration_start=rules.calibration_start.isoformat(), minimum_purge_minutes=rules.minimum_purge_minutes,
        extended_candidates={kind: rules.candidates(kind) for kind in ("logistic_l1", "svm_rbf")})
    (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    baseline = benchmark_predictions(frame, contract, benchmark)
    baseline["n_missing_feature_in_split"] = baseline.n_missing_rule_feature_in_split
    trend, trend_tuning = add_trend(frame)
    predictions = [baseline, trend]; tuning = []; interpretation = []; summaries = []; fitted = {}; audits = []
    for groups in feature_sets:
        for name in MODELS:
            LOGGER.info("fit_model model=%s feature_set=%s", name, "+".join(groups), extra={"model_kind": name, "feature_set": "+".join(groups)})
            if name in ("logistic_regression", "decision_tree"):
                result = train_supervised(frame, contract, supervised,
                    kind="logistic" if name == "logistic_regression" else "tree", feature_groups=groups)
            else:
                result = train_extended(frame, contract, rules, kind=name, feature_groups=groups)
                if not result.calibration_audit.empty:
                    audits.append(result.calibration_audit.assign(feature_set="+".join(groups)))
            predictions.append(result.predictions); tuning.append(result.tuning)
            interpretation.append(result.interpretation)
            summaries.extend(dict(model=name, feature_set="+".join(groups), **s) for s in result.summaries)
            fitted[name, "+".join(groups)] = result.fitted[30]
    pred = pd.concat(predictions, ignore_index=True)
    pred["experiment_version"] = rules.version; pred["result_status"] = STATUS
    for (_, _, split), part in pred.groupby(["model", "feature_set", "split"]):
        expected = set(frame.loc[frame.split.eq(split) & frame.label_30m.notna(), "event_id"])
        if not part.event_id.is_unique or set(part.event_id) != expected:
            raise ValueError("Models must predict identical known-label event cohorts")
    metrics, summary, confusion, selected = summarise_predictions(pred)
    tuning_table = pd.concat(tuning, ignore_index=True)
    chosen_params = tuning_table.loc[tuning_table.selected].copy()
    selection = selected.merge(chosen_params[["model", "feature_set", "parameters"]],
                                on=["model", "feature_set"], validate="one_to_one")
    explanation = pd.concat([table for table in interpretation if not table.empty], ignore_index=True)
    reference = compare_reference(pred, reference_path) if reference_path else {"status": "not_requested"}
    pred.to_parquet(output / "predictions.parquet", index=False)
    joblib.dump(fitted, output / "fitted_pipelines.joblib")
    tables = dict(metrics=metrics, metrics_summary=summary, confusion_matrices=confusion,
        tuning=tuning_table, selected_parameters=chosen_params, validation_selected=selection,
        interpretation=explanation, trend_rule_tuning=trend_tuning,
        calibration_audit=pd.concat(audits, ignore_index=True))
    errors, grouped_errors = error_diagnostics(pred, pd.read_parquet(events_path))
    errors.to_parquet(output / 'test_error_audit.parquet', index=False)
    tables['error_groups'] = grouped_errors
    tables['feature_group_comparisons'] = feature_gains(summary, feature_sets)
    for name, table in tables.items():
        table.to_csv(output / (name + ".csv"), index=False)
    (output / "model_summaries.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    if figures:
        plot_results(pred, summary, selected, explanation, output / "figures")
    code_files = [Path(__file__), Path(__file__).with_name("run_experiment.py"),
                  ROOT / "src/traffic_recovery/models/extended_classifiers.py",
                  ROOT / "src/traffic_recovery/models/supervised.py",
                  ROOT / "src/traffic_recovery/models/benchmarks.py",
                  ROOT / "src/traffic_recovery/models/evaluation.py",
                  ROOT / "src/traffic_recovery/models/contract.py",
                  ROOT / "src/traffic_recovery/models/provenance.py"]
    code_files.append(ROOT / 'src/traffic_recovery/models/experiment_diagnostics.py')
    recorded_at = datetime.now(timezone.utc)
    run_evidence = dict(run_id=run_id, started_at=started_at.isoformat(),
        recorded_at=recorded_at.isoformat(), runtime_seconds=time.perf_counter()-started,
        seed=rules.seed, git=git_state, lock={"file":"uv.lock","sha256":lock_hash},
        split_boundaries={"validation_start":contract.validation_start.isoformat(),
            "test_start":contract.test_start.isoformat(),"test_end":contract.test_end.isoformat()})
    manifest = dict(status=STATUS, completed=True, run=run_evidence, recorded_at=recorded_at.isoformat(),
        runtime_seconds=time.perf_counter() - started, inputs=inputs_record, contract_validation=validation,
        prediction_rows=len(pred), supervised_arms=len(fitted), candidate_base_fits=len(tuning_table),
        reference_comparison=reference, software=dict(python=platform.python_version(),
        pandas=pd.__version__, numpy=np.__version__, sklearn=sklearn.__version__),
        code_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in code_files},
        outputs_sha256={p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*") if p.is_file()})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path, help="Prepared event features; no raw-source reconstruction")
    parser.add_argument("--events", required=True, type=Path, help="Matching original event audit including outcome_maturity_at")
    parser.add_argument("--output-dir", required=True, type=Path, help="Must not already exist")
    parser.add_argument("--contract", type=Path, default=ROOT / "configs/tianhao_long_window_30m_contract.json")
    parser.add_argument("--rules", type=Path, default=ROOT / "configs/tianhao_extended_models.json")
    parser.add_argument("--supervised-rules", type=Path, default=ROOT / "configs/supervised_models.json")
    parser.add_argument("--benchmark-rules", type=Path, default=ROOT / "configs/benchmarks.json")
    parser.add_argument("--reference-predictions", type=Path, help="Optional notebook predictions; checked after training")
    parser.add_argument("--figures", action="store_true", help="Export PNG figures using a noninteractive backend")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run(dataset_path=args.dataset, events_path=args.events, contract_path=args.contract,
        rules_path=args.rules, supervised_rules_path=args.supervised_rules,
        benchmark_rules_path=args.benchmark_rules, output=args.output_dir,
        reference_path=args.reference_predictions, figures=args.figures)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
