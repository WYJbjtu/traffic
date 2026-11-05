"""Run versioned inferred-network retrospective experiment (never overwrite outputs).

Requires authenticated local PR #20 inputs. 2026 network is a retrospective
proxy for 2023–2026 observations; outputs do not certify legal connectivity.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from traffic_recovery.data.http import sha256_file
from traffic_recovery.models.expanded96 import LOCAL, HISTORY, candidate_models, metrics
from traffic_recovery.network.inferred_v2 import score_mappings, inferred_paths, spatial_features, inferred_transitions
from traffic_recovery.network.spatial96 import verify_release, verify_network

S1 = [f"{s}_{field}" for s in ("upstream", "downstream") for field in
      ("mean_speed_kmh", "mean_ratio", "observed_count", "mean_age_minutes", "coverage", "missing")]
S2 = [f"{s}_congestion_fraction" for s in ("upstream", "downstream")] + [
    "upstream_downstream_congestion_difference", "local_minus_neighbor_ratio", "neighbor_to_local_speed_gradient"]
S3 = [f"{s}_{field}" for s in ("upstream", "downstream") for field in
      ("mean_network_distance_m", "distance_weighted_speed", "confidence_weighted_speed", "multihop_congestion_fraction")]
S4 = [f"{s}_change_{i}m_kmh" for s in ("upstream", "downstream") for i in (5, 10, 15)] + ["local_neighbor_trend_difference"]
ARMS = {"M0": LOCAL + HISTORY, "M1": LOCAL + HISTORY + S1,
        "M2": LOCAL + HISTORY + S1 + S2, "M3": LOCAL + HISTORY + S1 + S2 + S3,
        "M4": LOCAL + HISTORY + S1 + S2 + S3 + S4,
        "M5": LOCAL + HISTORY + [f"{s}_mean_network_distance_m" for s in ("upstream", "downstream")]}


def evaluate(events: pd.DataFrame, feature: pd.DataFrame, population: str, *,
             arms: dict[str, list[str]] | None = None,
             eligible_ids: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Same known-label, observed-neighbor event IDs for every arm in population.

    Two fixed RF/XGB candidates per arm; validation log loss selects, without
    train+validation refit. Threshold .5 fixed. Never select on test outcomes.
    """
    data = events.merge(feature.drop(columns=["prediction_time"]), on="event_id", validate="one_to_one")
    eligible = data.observed_neighbor_count.gt(0) if eligible_ids is None else data.event_id.isin(eligible_ids)
    data = data.loc[data.label_30m.notna() & eligible].copy()
    if not all(set(data.loc[data.split_proposal.eq(s), "label_30m"].astype(int)) == {0, 1}
               for s in ("train", "validation", "test")):
        return pd.DataFrame(), pd.DataFrame()
    rows, tuning = [], []
    for arm, columns in (ARMS if arms is None else arms).items():
        if not set(columns).issubset(data):
            raise ValueError(f"Missing feature columns for {arm}: {set(columns)-set(data)}")
        train = data.loc[data.split_proposal.eq("train")]
        val = data.loc[data.split_proposal.eq("validation")]
        for model_name in ("random_forest", "xgboost"):
            contenders = candidate_models()[model_name]
            losses = []
            for idx, model in enumerate(contenders):
                model.fit(train[columns].to_numpy(dtype=float), train.label_30m.to_numpy(dtype=int))
                p = model.predict_proba(val[columns].to_numpy(dtype=float))[:, 1]
                from sklearn.metrics import log_loss
                loss = float(log_loss(val.label_30m.astype(int), np.clip(p, 1e-7, 1-1e-7)))
                losses.append(loss)
                tuning.append({"population": population, "arm": arm, "model": model_name,
                               "candidate": idx, "validation_log_loss": loss})
            choice = int(np.argmin(losses)); model = contenders[choice]
            for split in ("validation", "test"):
                subset = data.loc[data.split_proposal.eq(split)]
                y = subset.label_30m.to_numpy(dtype=int)
                p = model.predict_proba(subset[columns].to_numpy(dtype=float))[:, 1]
                row = {"population": population, "arm": arm, "model": model_name, "split": split,
                    "n_events": len(subset), "n_positive": int(sum(y)), "n_negative": int(len(y)-sum(y)),
                    "event_ids_sha256": hashlib.sha256("\n".join(sorted(subset.event_id)).encode()).hexdigest(),
                    "selected_candidate": choice, "features": "|".join(columns),
                    **metrics(y, p, (p >= .5).astype(int))}
                rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(tuning)


def run(archive: Path, release: Path, network: Path, output: Path, report: Path) -> None:
    if output.exists() or report.exists():
        raise FileExistsError("Refusing overwrite of versioned evidence")
    units, events, release_manifest = verify_release(archive, release)
    network_manifest = verify_network(network)
    previous = ROOT / "reports/spatial96_nov05"
    input_paths = [previous / "mapping_candidates96.parquet", ROOT / "data/local/spatial96/v1/candidate_path_evidence.parquet",
                   release / "processed/cohort_bins.parquet", release / "processed/events.parquet",
                   ROOT / "data/local/expanded96-release/model-a0-a2-v2/history_features.parquet"]
    if not all(p.exists() for p in input_paths):
        raise FileNotFoundError("PR #20 inputs or frozen expanded96 history missing")
    manifest_model = json.loads((input_paths[-1].parent / "manifest.json").read_text(encoding="utf-8"))
    if sha256_file(input_paths[-1]) != manifest_model["outputs_sha256"]["history_features.parquet"]:
        raise ValueError("Frozen local history hash mismatch")
    candidates = pd.read_parquet(input_paths[0]); raw_paths = pd.read_parquet(input_paths[1])
    ranking = score_mappings(candidates, units)
    with zipfile.ZipFile(archive) as z:
        references = pd.read_parquet(io.BytesIO(z.read("reports/full_january_reference.parquet")))
    events = events.merge(pd.read_parquet(input_paths[-1]), on="event_id", validate="one_to_one")
    if not events.feature_max_available_at.le(events.prediction_time).all() or not events.history_latest_available_at.dropna().le(events.loc[events.history_latest_available_at.notna(), "prediction_time"]).all():
        raise ValueError("Event/history availability violation")
    output.mkdir(parents=True); report.mkdir(parents=True)
    ranking.to_parquet(output / "mapping_scores.parquet", index=False)
    with sqlite3.connect(network / "topology_index.sqlite") as db:
        graph = inferred_transitions(db)
    graph.to_parquet(output / "inferred_directed_graph.parquet", index=False)
    graph_pairs = set(zip(graph.from_arc, graph.to_arc))
    quality = ranking.loc[ranking["rank"].eq(1) | ranking.quality_tier.eq("UNMATCHED")].copy()
    quality.to_csv(report / "map_matching_quality.csv", index=False)
    all_details, all_features, coverage, results, searches = [], [], [], [], []
    for population in ("INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED"):
        paths = inferred_paths(raw_paths, ranking, population)
        if not paths.empty:
            for seq in paths.arc_sequence:
                arcs = seq.split("|")
                if any((a, b) not in graph_pairs for a, b in zip(arcs, arcs[1:])):
                    raise ValueError("Inferred path not in intersection-supported graph")
        if paths.empty:
            coverage.extend({"population": population, "split": s, "status": "NO_PATH", "eligible_known": 0}
                            for s in ("train", "validation", "test"))
            continue
        paths.to_parquet(output / ("paths_" + population + ".parquet"), index=False)
        detail, features = spatial_features(events, paths, input_paths[2], references,
                                             bins_sha256=release_manifest["files"]["processed/cohort_bins.parquet"]["sha256"])
        all_details.append(detail); all_features.append(features)
        for s in ("train", "validation", "test"):
            subset = events.loc[events.split_proposal.eq(s)].merge(features[["event_id", "observed_neighbor_count"]], on="event_id", validate="one_to_one")
            eligible = subset.loc[subset.observed_neighbor_count.gt(0) & subset.label_30m.notna()]
            coverage.append({"population": population, "split": s, "status": "INFERRED_NOT_VERIFIED",
                "all_events": len(subset), "known_labels": int(subset.label_30m.notna().sum()),
                "eligible_known": len(eligible), "positive": int(eligible.label_30m.sum()),
                "negative": int(len(eligible) - eligible.label_30m.sum()),
                "detectors": int(eligible.detector_id.nunique()),
                "paths": int(paths.selected_path.sum()),
                "ambiguous_paths": int(paths.alternative_paths.gt(1).sum()),
                "observed_neighbor_events": int(subset.observed_neighbor_count.gt(0).sum())})
        model_results, tuning = evaluate(events, features, population)
        if not model_results.empty:
            results.append(model_results); searches.append(tuning)
    # Zero approvals stay isolated from inferred feature extraction.
    coverage.extend({"population": "INDEPENDENTLY_VERIFIED", "split": s, "status": "NO_GO_ZERO_APPROVALS",
                     "eligible_known": 0} for s in ("train", "validation", "test"))
    pd.DataFrame(coverage).to_csv(report / "network_coverage_by_split.csv", index=False)
    pd.concat([pd.read_parquet(output / f"paths_{p}.parquet").loc[lambda d:d.selected_path]
        for p in ("INFERRED_EXPLORATORY", "HIGH_CONFIDENCE_INFERRED")
        if (output / f"paths_{p}.parquet").exists()], ignore_index=True).to_parquet(
            output / "inferred_detector_neighbors.parquet", index=False)
    if all_details:
        pd.concat(all_details, ignore_index=True).to_parquet(output / "event_neighbor_lineage.parquet", index=False)
        pd.concat(all_features, ignore_index=True).to_parquet(output / "event_spatial_features.parquet", index=False)
    else:
        raise ValueError("No authentic as-of inferred neighbor observations")
    result = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    result.to_csv(report / "paired_spatial_metrics.csv", index=False)
    pd.concat(searches, ignore_index=True).to_csv(report / "experiment_matrix.csv", index=False) if searches else pd.DataFrame().to_csv(report / "experiment_matrix.csv", index=False)
    source = {str(p): sha256_file(p) for p in input_paths}
    source.update({"release_zip": sha256_file(archive),
                   **{k: v["sha256"] for k, v in network_manifest["sources"].items()}})
    (report / "source_sha256.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    outputs = {str(p.resolve().relative_to(ROOT)): sha256_file(p) for folder in (output, report)
               for p in folder.iterdir() if p.is_file()}
    (report / "output_sha256.json").write_text(json.dumps(outputs, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, default=Path("data/local/expanded96-release/HK_Traffic_Expanded_96_Prepared_Data_v1.zip"))
    p.add_argument("--release", type=Path, default=Path("data/local/expanded96-release/prepared-v1"))
    p.add_argument("--network", type=Path, default=Path("data/local/network-full/v1"))
    p.add_argument("--output", type=Path, default=Path("data/local/spatial96/inferred-v2"))
    p.add_argument("--report", type=Path, default=Path("reports/spatial96_inferred_v2"))
    a = p.parse_args()
    run(a.archive, a.release, a.network, a.output, a.report)

if __name__ == "__main__":
    main()
