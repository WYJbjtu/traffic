"""Fresh, gated RF/XGBoost/HGB 30m ablations on Tianhao's authenticated feature matrix.

Prepare with experiments/tianhao/run_release96.py prepare first. Never use saved
predictions/metrics as features. This script will not create an output directory
unless the Release, external cache, preparation hashes, and event alignment pass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments/tianhao"))
from traffic_recovery.models.contract import ExperimentContract, validate_event_table
from traffic_recovery.models.expanded96 import candidate_models, metrics
from run_release96 import verify_release, verify_sources, sha, traffic_file, CONTRACT

MODELS = ("random_forest", "xgboost", "hist_gradient_boosting")
GROUPS = (("local",), ("local", "history"),
          ("local", "history", "calendar"),
          ("local", "history", "calendar", "weather"))
EXPECTED_SPLITS = {"train": 13002, "validation": 7848, "test": 7008}
EXPECTED_EVENT_COUNT = 30452


def aligned_features(features: pd.DataFrame, events: pd.DataFrame, contract: ExperimentContract) -> pd.DataFrame:
    """Reject any mismatch in event identity, time, target, unit or split; return known rows.

    Missing/censored labels stay excluded, never converted to negatives. Both frames
    must carry HKT-aware datetimes. Contract also enforces temporal purges and
    activated feature-availability watermarks.
    """
    validate_event_table(features, contract)
    if len(features) != len(events) or len(events) != EXPECTED_EVENT_COUNT or events.event_id.duplicated().any():
        raise ValueError("Frozen 96-lane event count/identity mismatch")
    if events.definition_version.nunique() != 1 or events.definition_version.iloc[0] != "lane-observed-confirmation-v1":
        raise ValueError("Wrong recovery confirmation definition")
    if features.event_id.isna().any() or set(features.event_id) != set(events.event_id):
        raise ValueError("Feature and Release event IDs differ")
    reference = events.set_index("event_id").loc[features.event_id].reset_index()
    for left, right in (("prediction_time", "prediction_time"), ("split", "split_proposal"),
                        ("label_30m", "label_30m"), ("detector_id", "detector_id"),
                        ("direction", "direction"), ("lane_id", "lane_id")):
        if left not in features or not features[left].reset_index(drop=True).equals(reference[right].reset_index(drop=True)):
            raise ValueError(f"Release/feature alignment mismatch: {left}")
    known = features.loc[features.label_30m.notna()].copy()
    if known.split.value_counts().to_dict() != EXPECTED_SPLITS:
        raise ValueError("Frozen known-label split counts differ")
    return known


def run(*, release_dir: Path, source_cache: Path, prepared_dir: Path, output: Path) -> None:
    """Fit fixed two-candidate budgets on train; select by validation log loss only.

    Uses Tianhao's *full rebuilt* event_features.parquet, not committed summaries.
    Preprocessing pipelines are fit on training data only; no post-selection refit.
    Output includes independent row-level probabilities and hash manifest; binaries
    remain local. Any incomplete source cache or changed preparation is an error.
    """
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    verify_release(release_dir)
    sources = verify_sources(source_cache)
    preparation = json.loads((prepared_dir / "manifest.json").read_text(encoding="utf-8"))
    if (preparation.get("status") != "passed" or preparation.get("events") != 30452
            or preparation.get("release_manifest_sha256") != sha(release_dir / "SHARED_DATA_MANIFEST.json")
            or preparation.get("lock_sha256") != sha(ROOT / "uv.lock")):
        raise ValueError("Preparation provenance differs from current Release/lock")
    for name, digest in preparation["code_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Preparation code changed: {name}")
    for name, digest in preparation["outputs_sha256"].items():
        if sha(prepared_dir / name) != digest:
            raise ValueError(f"Prepared artifact changed: {name}")
    staged_sources = pd.read_csv(prepared_dir / "sources.csv").to_dict("records")
    if staged_sources != sources:
        raise ValueError("Preparation and current external source provenance differ")
    if sha(prepared_dir / "contract.json") != sha(CONTRACT):
        raise ValueError("Feature contract changed")
    contract = ExperimentContract.from_path(CONTRACT)
    if contract.horizons != (30,) or tuple(contract.feature_groups) != GROUPS[-1]:
        raise ValueError("Unexpected feature groups or target horizon")
    frame = aligned_features(pd.read_parquet(prepared_dir / "event_features.parquet"),
                             pd.read_parquet(traffic_file(release_dir, "events.parquet")), contract)
    missing = set(contract.feature_allowlist) - set(frame.columns)
    if missing:
        raise ValueError(f"Incomplete rebuilt feature matrix: {sorted(missing)}")
    tuning, predictions, summaries = [], [], []
    for groups in GROUPS:
        columns = [c for group in groups for c in contract.feature_groups[group]]
        name = "+".join(groups)
        for split in EXPECTED_SPLITS:
            if frame.loc[frame.split.eq(split), columns].isna().all().any():
                raise ValueError(f"Entire feature column missing in {split}/{name}")
        subsets = {split: frame.loc[frame.split.eq(split)] for split in EXPECTED_SPLITS}
        xs = {s: part[columns].to_numpy(dtype=float) for s, part in subsets.items()}
        ys = {s: part.label_30m.to_numpy(dtype=int) for s, part in subsets.items()}
        for model_name in MODELS:
            candidates = candidate_models()[model_name]
            scores = []
            for i, model in enumerate(candidates):
                model.fit(xs["train"], ys["train"])
                prob = model.predict_proba(xs["validation"])[:, 1]
                score = float(log_loss(ys["validation"], np.clip(prob, 1e-7, 1-1e-7), labels=[0, 1]))
                scores.append(score)
                tuning.append(dict(model=model_name, feature_set=name, candidate=i, validation_log_loss=score))
            winner = int(np.argmin(scores))
            for split in ("validation", "test"):
                part = subsets[split]
                prob = candidates[winner].predict_proba(xs[split])[:, 1]
                pred = (prob >= .5).astype(int)
                predictions.append(pd.DataFrame(dict(event_id=part.event_id.to_numpy(),
                    prediction_time=part.prediction_time.to_numpy(), split=split, model=model_name,
                    feature_set=name, label=ys[split], probability=prob, prediction=pred)))
                summaries.append(dict(model=model_name, feature_set=name, split=split,
                    n_known=len(part), selected_candidate=winner, **metrics(ys[split], prob, pred)))
    output.mkdir(parents=True)  # only after input gates; never overwrite historical outputs
    pd.concat(predictions, ignore_index=True).to_parquet(output / "predictions.parquet", index=False)
    pd.DataFrame(summaries).to_csv(output / "model_metrics.csv", index=False)
    pd.DataFrame(tuning).to_csv(output / "tuning.csv", index=False)
    manifest = dict(status="EXPLORATORY; prior test exposure; no scientific approval",
        target="recovery_confirmation_v1", cohort="expanded96-long-window-v1", horizon_minutes=30,
        preparation_manifest_sha256=sha(prepared_dir / "manifest.json"),
        release_manifest_sha256=sha(release_dir / "SHARED_DATA_MANIFEST.json"),
        source_cache_metadata=sources, contract_sha256=sha(CONTRACT),
        script_sha256=sha(Path(__file__)), lock_sha256=sha(ROOT / "uv.lock"),
        feature_sets={"+".join(g): [c for x in g for c in contract.feature_groups[x]] for g in GROUPS},
        selection="two fixed candidates/model; minimum validation log loss; no refit; threshold 0.5",
        created_at=datetime.now(timezone.utc).isoformat(),
        outputs_sha256={name: sha(output / name) for name in ("predictions.parquet", "model_metrics.csv", "tuning.csv")})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("release-dir", "source-cache", "prepared-dir", "output"):
        parser.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args()
    run(release_dir=args.release_dir, source_cache=args.source_cache,
        prepared_dir=args.prepared_dir, output=args.output)


if __name__ == "__main__":
    main()
