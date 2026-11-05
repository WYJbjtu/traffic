"""Append official source review evidence to an already-generated spatial96 package.

Adds new filenames only: preserves the first run's hashed evidence unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from traffic_recovery.data.http import sha256_file
from traffic_recovery.network.pilot import read_features


def run(report: Path, network: Path, processed: Path) -> dict:
    """Read historical snapshots and relevant source TURN/INTERSECTION records."""
    selected = pd.read_csv(report/"candidate_directed_pairs.csv",dtype={"route_sequence":str,"arc_sequence":str})
    chosen = selected.loc[selected.intersection_ids.notna()].head(6)
    if len(chosen) < 1: raise ValueError("No intersection-supported pair available for review")
    candidates = pd.read_parquet(report/"mapping_candidates96.parquet")
    summary = pd.read_csv(report/"mapping_summary.csv")
    network_manifest=json.loads((network/"manifest.json").read_text(encoding="utf-8"))
    routes={route for seq in chosen.route_sequence for route in seq.split("|")}
    ids={str(i) for seq in chosen.intersection_ids for i in str(seq).split("|")}
    intersection_file=Path(network_manifest["sources"]["INTERSECTION.gml"]["path"])
    turn_file=Path(network_manifest["sources"]["TURN.gml"]["path"])
    intersections=[a for a,_ in read_features(intersection_file) if a.get("INT_ID") in ids]
    turns=[a for a,_ in read_features(turn_file) if any(a.get(f"EDGE{i}FID") in routes for i in range(1,9))]
    # This is a bounded audit of two stored samples, not a historical series.
    speeds = []
    for date in ("20230515-1200", "20260915-1200"):
        path=processed/f"observations_{date}.parquet"
        frame=pd.read_parquet(path)
        if frame.irn_version.nunique()!=1 or frame.irn_version.iloc[0]!="20221210":
            raise ValueError("Unexpected processed snapshot network version")
        speeds.append(dict(snapshot=date,raw_xml_sha256=frame.source_hash.iloc[0],
            raw_xml_current_sha256=sha256_file(processed/"http"/f"segment_{date}.xml"),
            segment_rows=len(frame), source_valid_numeric=int((frame.source_valid & frame.speed_kmh.notna()).sum()),
            selected_candidate_route_id_overlap=int(frame.segment_id.isin(routes).sum()),
            source_irn_version=frame.irn_version.iloc[0], historical_geometry_compatible=int(frame.network_compatible.sum()),
            approved_for_neighbor_model=int(frame.usable_for_historical_features.sum()),
            available_at_min=frame.available_at.min().isoformat(),observed_at_min=frame.observed_at.min().isoformat(),
            interpretation="ID overlap only; raw/processed dependence unknown; two isolated snapshots"))
    if any(r["raw_xml_sha256"]!=r["raw_xml_current_sha256"] for r in speeds):
        raise ValueError("Processed XML provenance mismatch")
    old=pd.read_csv(ROOT/"reports/spatial_pair_review/pair_review_index.csv")
    frozen=set(summary.detector_id)
    pairs={(r.upstream_detector,r.downstream_detector) for r in selected.itertuples()}
    old["both_detectors_in_frozen96"]=[a in frozen and b in frozen for a,b in zip(old.upstream_candidate,old.downstream_candidate)]
    old["directed_pair_rediscovered_current_candidates"]=[(a,b) in pairs for a,b in zip(old.upstream_candidate,old.downstream_candidate)]
    proximity=pd.read_csv(ROOT/"reports/lane_expansion_continuity/detector_proximity_review_leads.csv")
    geographic=proximity.loc[proximity.distance_m_hk1980.le(250) & proximity.detector_a.isin(frozen)&proximity.detector_b.isin(frozen)]
    source = {name: network_manifest["sources"][name] for name in ("CENTERLINE.gml","INTERSECTION.gml","TURN.gml")}
    for name in ("selected_pair_intersections.csv","selected_pair_turns.csv","historical_processed_speed_audit.csv",
                 "previous_pair_overlap96.csv","geographic_review_leads_250m.csv","selected_pair_review_details.md"):
        if (report/name).exists(): raise FileExistsError(report/name)
    pd.DataFrame(intersections).to_csv(report/"selected_pair_intersections.csv",index=False)
    pd.DataFrame(turns).to_csv(report/"selected_pair_turns.csv",index=False)
    pd.DataFrame(speeds).to_csv(report/"historical_processed_speed_audit.csv",index=False)
    old.to_csv(report/"previous_pair_overlap96.csv",index=False)
    geographic.to_csv(report/"geographic_review_leads_250m.csv",index=False)
    details=["# Six candidate connection packets — additional official-source evidence", "",
        "Every path remains CANDIDATE_ONLY_NOT_MODEL_APPROVED. All six maps use actual official EPSG:2326 road lines, not straight detector links.",
        "No legal turn or 2023–September 2026 historical validity is certified. Reviewer fields in pair-*.md are intentionally blank.",""]
    for i,p in enumerate(chosen.itertuples(),1):
        details += [f"## Selected candidate {i}: {p.upstream_detector} → {p.downstream_detector}",
            f"Map and blank decision checklist: [pair-{i}.md](pair-{i}.md), [pair-{i}.png](pair-{i}.png).",
            f"Arc path: `{p.arc_sequence}`; road routes: `{p.route_sequence}`; endpoint evidence: `{p.node_sequence}`; distance {p.path_distance_m:.1f} m.",
            f"Source intersection IDs: `{p.intersection_ids}`. All nearby TURN records involving selected routes: [selected_pair_turns.csv](selected_pair_turns.csv); do not infer permission from missing prohibitions.",""]
        for detector,arc in ((p.upstream_detector,p.from_arc),(p.downstream_detector,p.to_arc)):
            matches=candidates.loc[candidates.detector_id.eq(detector)&candidates.arc_id.eq(arc)]
            if matches.empty:
                details += [f"- {detector} arc {arc}: mapping not found, independent review required."]
                continue
            r=matches.sort_values("distance_m").iloc[0]
            details += [f"- {detector} {r.direction}/{r.lane_id}: detector description `{r.detector_description}`; candidate road `{r.road_name}` (route {r.route_id}), "
                f"point-line {r.distance_m:.1f} m, tangent error {r.directional_error_deg:.1f}°, source travel direction {r.travel_direction}, grade code {r.elevation}, "
                f"last source road update `{r.road_source_last_updated}`, metadata direction agrees {r.metadata_direction_agrees}, parallel/grade risk {r.parallel_or_grade_risk}, name check {r.name_evidence}."]
        details += ["- Independent reviewer: ______   Decision: ______   Evidence/valid interval: ______", "- Check both carriageways, tunnel/bridge level, real turn conditions, historical network version, installation/replacement dates and raw/processed independence.",""]
    details += ["## Source provenance", ""]
    for key,item in source.items():
        details += [f"- `{key}` official URL {item['url']} SHA-256 `{item['sha256']}`, retrieved {item['http_metadata']['retrieved_at']}, HTTP Last-Modified {item['http_metadata']['headers'].get('last-modified','not provided')}."]
    details += ["- Detector metadata SHA-256: see evidence_manifest.json; original detector metadata source date not stated in Release CSV.",
        "- Processed snapshots `irn_version=20221210` vs current October 2026 geometry: ID overlap alone is not historical compatibility. [Audit](historical_processed_speed_audit.csv).",
        "- Earlier six review leads: [overlap](previous_pair_overlap96.csv); 29 current frozen96 geographic <=250m leads: [CSV](geographic_review_leads_250m.csv). Proximity alone cannot establish a road connection.",""]
    (report/"selected_pair_review_details.md").write_text("\n".join(details),encoding="utf-8")
    return dict(official_intersections=len(intersections),nearby_turn_records=len(turns),
        prior_pairs_fully_overlap=int(old.both_detectors_in_frozen96.sum()),
        prior_pairs_rediscovered=int(old.directed_pair_rediscovered_current_candidates.sum()),
        geographic_pairs_within_250m=len(geographic),processed_snapshots=speeds)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    parser.add_argument("--network",type=Path,default=Path("data/local/network-full/v1"))
    parser.add_argument("--processed",type=Path,default=Path("data/local/processed-pilot/v1"))
    parser.add_argument("--hash-only",action="store_true",help="Hash newly added review files after a successful run")
    a=parser.parse_args()
    if a.hash_only:
        from traffic_recovery.data.http import sha256_file
        target=a.report/"review_evidence_manifest.json"
        if target.exists(): raise FileExistsError(target)
        names=["selected_pair_intersections.csv","selected_pair_turns.csv","historical_processed_speed_audit.csv",
               "previous_pair_overlap96.csv","geographic_review_leads_250m.csv","selected_pair_review_details.md"]
        manifest={name:sha256_file(a.report/name) for name in names}
        target.write_text(json.dumps({"status":"candidate_review_no_human_approval","sha256":manifest},indent=2)+"\n",encoding="utf-8")
        print(json.dumps(manifest,indent=2))
    else: print(json.dumps(run(a.report,a.network,a.processed),indent=2))

if __name__=="__main__": main()
