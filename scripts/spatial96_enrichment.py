"""Append candidate corridor coverage rankings and bounded disconnection leads.

Consumes authentic earlier outputs, never approves candidate relationships or alters
original run's hash manifest. New files only; ranks without test model performance.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def run(report: Path, local: Path) -> dict:
    """Rank corridor leads by source evidence and genuine as-of availability."""
    for name in ("candidate_corridor_coverage_ranking.csv","candidate_detector_disconnections.csv"):
        if (report/name).exists(): raise FileExistsError(report/name)
    pairs=pd.read_csv(report/"candidate_directed_pairs.csv",dtype={"route_sequence":str})
    mapping=pd.read_csv(report/"mapping_summary.csv")
    coverage=pd.read_csv(local/"candidate_neighbor_coverage.csv",usecols=["event_id","split","label_known_30m",
        "downstream_available_speed_count"])
    import pyarrow.parquet as pq
    # Read only exact source event identity and split to attach detector to the
    # candidate coverage row; do not rely on a prediction table from another run.
    events=pq.read_table(Path("data/local/expanded96-release/prepared-v1/processed/events.parquet"),
        columns=["event_id","detector_id","split_proposal"]).to_pandas()
    events=events.merge(coverage,on="event_id",validate="one_to_one")
    if not events.split_proposal.eq(events.split).all():raise ValueError("Release/coverage split mismatch")
    features=events.groupby("detector_id").agg(event_count=("event_id","size"),
        candidate_downstream_asof=("downstream_available_speed_count",lambda v:int(v.gt(0).sum())),
        train_events=("split",lambda s:int(s.eq("train").sum())),
        validation_events=("split",lambda s:int(s.eq("validation").sum())),
        test_events=("split",lambda s:int(s.eq("test").sum())))
    grouped=pairs.groupby("route_sequence",as_index=False).agg(
        candidate_directed_pairs=("upstream_detector","size"),
        distinct_upstream=("upstream_detector","nunique"),distinct_downstream=("downstream_detector","nunique"),
        intersection_supported=("intersection_ids",lambda s:int(s.notna().sum())),
        minimum_network_m=("path_distance_m","min"))
    upstream=pairs[["route_sequence","upstream_detector"]].drop_duplicates().merge(features,left_on="upstream_detector",right_index=True,how="left")
    evidence=upstream.groupby("route_sequence")[list(features.columns)].sum().reset_index()
    grouped=grouped.merge(evidence,on="route_sequence",validate="one_to_one")
    flags=mapping.set_index("detector_id")[["ambiguous","direction_conflict"]]
    corridor_detectors=pairs[["route_sequence","upstream_detector"]].rename(columns={"upstream_detector":"detector_id"})
    corridor_detectors=pd.concat([corridor_detectors,pairs[["route_sequence","downstream_detector"]].rename(columns={"downstream_detector":"detector_id"})]).drop_duplicates()
    flags= corridor_detectors.merge(flags,left_on="detector_id",right_index=True,validate="many_to_one")
    risk=flags.groupby("route_sequence").agg(ambiguous_detector_units=("ambiguous","sum"),
        direction_conflict_units=("direction_conflict","sum")).reset_index()
    grouped=grouped.merge(risk,on="route_sequence",validate="one_to_one")
    grouped["historical_approval"]="none;2026_geometry_not_validated_for_2023_2026"
    grouped["ranking_policy"]="distinct_detector_count;intersection;actual_asof_coverage;risk;never_test_score"
    grouped=grouped.sort_values(["distinct_upstream","distinct_downstream","intersection_supported",
        "candidate_downstream_asof","ambiguous_detector_units","direction_conflict_units"],
        ascending=[False,False,False,False,True,True])
    grouped.to_csv(report/"candidate_corridor_coverage_ranking.csv",index=False)
    # At most 1 km Euclidean prefilter for review of failures; geometric distance
    # is never treated as directed connectivity.
    ids=mapping.drop_duplicates("detector_id").set_index("detector_id")
    found={(r.upstream_detector,r.downstream_detector) for r in pairs.itertuples()}
    disconnected=[]
    for a in ids.itertuples():
        if not a.candidate_matched: continue
        for b in ids.itertuples():
            if a.Index==b.Index or not b.candidate_matched or (a.Index,b.Index) in found:continue
            if pd.isna(a.easting) or pd.isna(b.easting):continue
            d=((a.easting-b.easting)**2+(a.northing-b.northing)**2)**.5
            if d <= 1000:
                disconnected.append(dict(from_detector=a.Index,to_detector=b.Index,point_distance_m=d,
                    search_result="no_candidate_directed_path_within_1000m_5arcs",
                    caveat="not_proof_of_no_legal_connection;candidate_road_ambiguity_or_turn_restriction_possible"))
    pd.DataFrame(disconnected).to_csv(report/"candidate_detector_disconnections.csv",index=False)
    return dict(corridors=len(grouped),disconnection_review_leads=len(disconnected))


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    parser.add_argument("--local",type=Path,default=Path("data/local/spatial96/v1"))
    parser.add_argument("--hash-only",action="store_true")
    a=parser.parse_args()
    if a.hash_only:
        from traffic_recovery.data.http import sha256_file
        import json
        target=a.report/"enrichment_evidence_manifest.json"
        if target.exists():raise FileExistsError(target)
        outputs={name:sha256_file(a.report/name) for name in
            ("candidate_corridor_coverage_ranking.csv","candidate_detector_disconnections.csv")}
        target.write_text(json.dumps({"status":"candidate_only","input_coverage_sha256":sha256_file(a.local/"candidate_neighbor_coverage.csv"),
            "outputs_sha256":outputs},indent=2)+"\n",encoding="utf-8")
        print(outputs)
    else: print(run(a.report,a.local))

if __name__=="__main__":main()
