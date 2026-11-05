"""Run 96-lane official matching, directed discovery, and empirical as-of coverage.

No classifier training without independent mapping, turn and historical approval.
Default outputs are fresh and never overwrite historical experiment evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from traffic_recovery.data.http import sha256_file
from traffic_recovery.network.spatial96 import (ZIP_SHA, UNIT, verify_release, verify_network,
    geometry_near, match_units, directed_paths, detector_geojson)
from traffic_recovery.network.spatial96_coverage import candidate_opportunity, verified_zero_eligibility


def draw_packets(pairs: pd.DataFrame, summary: pd.DataFrame, geometries: dict, folder: Path,
                 db: sqlite3.Connection, manifest: dict) -> list[dict]:
    """Actual route geometries; blank human decision fields remain blank."""
    packets = []
    for index, row in enumerate(pairs.head(6).itertuples(index=False),1):
        routes = row.route_sequence.split("|")
        fig, ax = plt.subplots(figsize=(9,7))
        for route in set(routes):
            line = geometries[route]
            x,y = line.xy
            ax.plot(x,y,linewidth=2,label=f"Official route {route}")
        endpoints = summary.loc[summary.detector_id.isin([row.upstream_detector,row.downstream_detector])].drop_duplicates("detector_id")
        for p in endpoints.itertuples():
            ax.scatter([p.easting],[p.northing],s=65)
            ax.annotate(f"{p.detector_id} ({p.direction})",(p.easting,p.northing),fontsize=9)
        ax.set_aspect("equal");ax.legend(fontsize=7)
        ax.set(title=f"Candidate directed path {index}: {row.upstream_detector} -> {row.downstream_detector}\nNOT historical/legal approval",
               xlabel="Official EPSG:2326 Easting (m)",ylabel="Northing (m)")
        fig.tight_layout();fig.savefig(folder / f"pair-{index}.png",dpi=140);plt.close(fig)
        turn_records = []
        for a,b in zip(routes,routes[1:]):
            turn_records += list(db.execute("SELECT turn_id FROM restrictions WHERE from_route=? AND to_route=?",(a,b)))
        packet = dict(packet=index, upstream_detector=row.upstream_detector, downstream_detector=row.downstream_detector,
            upstream_lane=row.upstream_lane,downstream_lane=row.downstream_lane,arc_sequence=row.arc_sequence,
            route_sequence=row.route_sequence, node_sequence=row.node_sequence,
            source_intersection_ids=row.intersection_ids, restricting_turn_ids="|".join(x[0] for x in turn_records),
            network_distance_m=row.path_distance_m, independent_reviewer="", reviewer_decision="",
            historical_valid_from="",historical_valid_to="", road_source_sha256=manifest["sources"]["CENTERLINE.gml"]["sha256"],
            intersection_source_sha256=manifest["sources"]["INTERSECTION.gml"]["sha256"],
            turn_source_sha256=manifest["sources"]["TURN.gml"]["sha256"],
            uncertainty_checklist="lane_identity;carriageway;direction;grade;intersection;turn_conditions;parallel_route;historical_version;measurement_independence")
        packets.append(packet)
        (folder/f"pair-{index}.md").write_text("# Official road connection candidate — not approved\n\n"+
            "\n".join(f"- {k}: {v}" for k,v in packet.items())+
            "\n\nMap: pair-%d.png (actual official line geometry, not detector-to-detector straight line).\n"%index+
            "Source TURN prohibition check is conservative; no listed prohibition does NOT establish legal turning.\n"
            "2026 geometry and 2023–2026 detector identity/route versions require independent evidence.\n",
            encoding="utf-8")
    return packets


def run(archive: Path, release: Path, network: Path, output: Path, report: Path) -> dict:
    """Authenticate all inputs before creating fresh result/report folders."""
    if output.exists() or report.exists():
        raise FileExistsError("Refusing to overwrite spatial96 evidence")
    units,events,release_manifest = verify_release(archive,release)
    network_manifest = verify_network(network)
    metadata = pd.read_csv(release / "metadata/detectors.csv",dtype={"AID_ID_Number":str},encoding="utf-8-sig")
    selected = units.merge(metadata,left_on="detector_id",right_on="AID_ID_Number",how="left",validate="many_to_one")
    pts = [Point(r.Easting,r.Northing) for r in selected.itertuples() if pd.notna(r.Easting) and pd.notna(r.Northing)]
    attrs,lines = geometry_near(network,pts)
    candidates,summary = match_units(units,metadata,attrs,lines,
        version="centerline-sha256:"+network_manifest["sources"]["CENTERLINE.gml"]["sha256"])
    lookup = {a["ROUTE_ID"]: line for a,line in zip(attrs,lines)}
    db = sqlite3.connect(network / "topology_index.sqlite")
    try:
        paths, rejected = directed_paths(db,candidates,lookup)
        if paths.empty:
            raise ValueError("No candidate paths; review matching/topology before coverage")
        paths = paths.sort_values(["path_distance_m","arc_count","upstream_detector","downstream_detector"])
        unique = paths.drop_duplicates(["upstream_detector","upstream_direction","upstream_lane",
            "downstream_detector","downstream_direction","downstream_lane"])
        # Rank only source evidence, geometry and coverage, never test model outcomes.
        corridor = unique.groupby("route_sequence",as_index=False).agg(
            candidate_directed_pairs=("upstream_detector","size"),
            distinct_upstream=("upstream_detector","nunique"),distinct_downstream=("downstream_detector","nunique"),
            minimum_network_m=("path_distance_m","min"))
        corridor["intersection_supported_paths"] = corridor.route_sequence.map(
            paths.groupby("route_sequence").intersection_ids.apply(lambda s: int(s.ne("").sum())))
        corridor = corridor.sort_values(["distinct_upstream","distinct_downstream","intersection_supported_paths","candidate_directed_pairs"],ascending=False)
        output.mkdir(parents=True); report.mkdir(parents=True)
        summary.to_csv(report / "mapping_summary.csv",index=False)
        candidates.to_parquet(report / "mapping_candidates96.parquet",index=False)
        summary.loc[summary.ambiguous | summary.direction_conflict | ~summary.candidate_matched].to_csv(report / "mapping_ambiguities.csv",index=False)
        (report / "detector_locations.geojson").write_text(json.dumps(detector_geojson(summary),ensure_ascii=False),encoding="utf-8")
        paths.to_parquet(output / "candidate_path_evidence.parquet",index=False)
        unique.to_csv(report / "candidate_directed_pairs.csv",index=False)
        corridor.to_csv(report / "candidate_corridors.csv",index=False)
        rejected.to_csv(report / "rejected_connections.csv",index=False)
        # Compare fixed discovery limits; never choose a range using model metrics.
        sensitivity = pd.DataFrame([{"max_distance_m":distance,"max_arcs":hops,
            "candidate_pairs":int(paths.loc[paths.path_distance_m.le(distance) & paths.arc_count.le(hops),
              ["upstream_detector","downstream_detector"]].drop_duplicates().shape[0])}
            for distance in (250,500,1000) for hops in (2,3,5)])
        sensitivity.to_csv(report/"candidate_path_sensitivity.csv",index=False)
        # Prior review leads are not automatically approved in this cohort.
        old = pd.read_csv(ROOT / "reports/spatial_pair_review/pair_review_index.csv")
        old.to_csv(report/"previous_review_leads_unverified.csv",index=False)
        draw_packets(unique.loc[unique.intersection_ids.ne("")].head(6) if unique.intersection_ids.ne("").any() else unique.head(6),
                     summary,lookup,report,db,network_manifest)
    finally: db.close()
    with zipfile.ZipFile(archive) as z:
        references = pd.read_parquet(__import__('io').BytesIO(z.read("reports/full_january_reference.parquet")))
    coverage = candidate_opportunity(events,paths,release / "processed/cohort_bins.parquet",references)
    coverage.to_csv(output / "candidate_neighbor_coverage.csv",index=False)
    verified = verified_zero_eligibility(events,references,version="centerline-sha256:"+network_manifest["sources"]["CENTERLINE.gml"]["sha256"])
    verified.to_parquet(output / "spatial_event_eligibility.parquet",index=False)
    groups = []
    for split in ("train","validation","test"):
        c=coverage.loc[coverage.split.eq(split)]
        v=verified.loc[verified.split.eq(split)]
        groups.append({"split":split,"all_events":len(c),"known_30m":int(c.label_known_30m.sum()),
            "candidate_any_asof":int(c.valid_observed_neighbor_detector_count.gt(0).sum()),
            "candidate_upstream_asof":int(c.upstream_available_speed_count.gt(0).sum()),
            "candidate_downstream_asof":int(c.downstream_available_speed_count.gt(0).sum()),
            "candidate_both_asof":int((c.upstream_available_speed_count.gt(0)&c.downstream_available_speed_count.gt(0)).sum()),
            "candidate_known_any_asof":int((c.valid_observed_neighbor_detector_count.gt(0)&c.label_known_30m).sum()),
            "verified_eligible_all":int(v.spatial_model_eligible.sum()),
            "verified_eligible_known":int((v.spatial_model_eligible & v.label_known_30m).sum())})
    eligibility = pd.DataFrame(groups)
    eligibility.to_csv(report/"spatial_eligibility_summary.csv",index=False)
    stats = {"cohort_units":len(units),"units_with_events":events[UNIT].drop_duplicates().shape[0],
        "events":len(events),"units_with_coordinates":int(summary.easting.notna().sum()),
        "candidate_matched_units":int(summary.candidate_matched.sum()),
        "one_plausible_candidate":int(summary.plausible_count.eq(1).sum()),
        "multiple_plausible_candidates":int(summary.plausible_count.gt(1).sum()),
        "ambiguous_within_10m":int(summary.ambiguous.sum()),
        "direction_conflict_units":int(summary.direction_conflict.sum()),
        "unmatched":int((~summary.candidate_matched).sum()),
        "candidate_directed_unit_pairs":len(unique),
        "candidate_directed_detector_pairs":int(unique[["upstream_detector","downstream_detector"]].drop_duplicates().shape[0]),
        "human_verified_mappings":0,"approved_relationships":0,
        "candidate_any_asof_events":int(coverage.valid_observed_neighbor_detector_count.gt(0).sum()),
        "verified_eligible_events":int(verified.spatial_model_eligible.sum()),
        "network_source_sha256":{k:v["sha256"] for k,v in network_manifest["sources"].items()},
        "release_zip_sha256":ZIP_SHA,
        "release_files_sha256":{k:v["sha256"] for k,v in release_manifest["files"].items()},
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "local_artifact_sha256":{p.name:sha256_file(p) for p in output.iterdir() if p.is_file()},
        "committed_artifact_sha256":{p.name:sha256_file(p) for p in report.iterdir() if p.is_file()}}
    (report/"evidence_manifest.json").write_text(json.dumps(stats,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return stats


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,default=Path("data/local/expanded96-release/HK_Traffic_Expanded_96_Prepared_Data_v1.zip"))
    parser.add_argument("--release",type=Path,default=Path("data/local/expanded96-release/prepared-v1"))
    parser.add_argument("--network",type=Path,default=Path("data/local/network-full/v1"))
    parser.add_argument("--output",type=Path,default=Path("data/local/spatial96/v1"))
    parser.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    a=parser.parse_args()
    print(json.dumps(run(a.archive,a.release,a.network,a.output,a.report),indent=2))

if __name__=="__main__": main()
