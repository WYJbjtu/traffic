"""Independent-review forms for six evidence-ranked, still-unapproved road pairs."""
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


def run(report:Path,network:Path) -> None:
    """Write new records; never overwrite the first-pass map or frozen manifest."""
    pairs=pd.read_csv(report/"ranked_pair_selection.csv",dtype=str,keep_default_na=False)
    matches=pd.read_parquet(report/"mapping_candidates96.parquet")
    roads=json.loads((network/"manifest.json").read_text(encoding="utf-8"))["sources"]
    intersection_ids={v for s in pairs.intersection_ids for v in s.split("|")}
    route_ids={v for s in pairs.route_sequence for v in s.split("|")}
    intersection=[r for r,_ in read_features(Path(roads["INTERSECTION.gml"]["path"])) if r.get("INT_ID") in intersection_ids]
    turns=[r for r,_ in read_features(Path(roads["TURN.gml"]["path"])) if any(r.get(f"EDGE{i}FID") in route_ids for i in range(1,9))]
    files=[report/"ranked_pair_intersections.csv",report/"ranked_pair_turns.csv"]
    files += [report/f"ranked-pair-{i}.md" for i in range(1,7)]
    files += [report/"ranked_packet_manifest.json"]
    if any(p.exists() for p in files):raise FileExistsError("Refusing to overwrite ranked packet evidence")
    pd.DataFrame(intersection).to_csv(files[0],index=False)
    pd.DataFrame(turns).to_csv(files[1],index=False)
    for i,p in enumerate(pairs.itertuples(index=False),1):
        fields=["# Evidence-ranked official road candidate — independent review needed", "",
            f"Source direction map: [ranked-directed-pair-{i}.png](ranked-directed-pair-{i}.png). Original official LineStrings in EPSG:2326; no straight-line road inference.",
            f"Detectors: `{p.upstream_detector}` ({p.upstream_direction}/{p.upstream_lane}) → `{p.downstream_detector}` ({p.downstream_direction}/{p.downstream_lane}).",
            f"Arcs: `{p.arc_sequence}`; source routes `{p.route_sequence}`; endpoint keys `{p.node_sequence}`.",
            f"Source INTERSECTION IDs `{p.intersection_ids}`; candidate path length `{p.path_distance_m}` m (distance along projected source geometry, excludes point-to-road offsets).",
            f"Candidate evidence score `{p.evidence_score}`; ranking uses names, point distances, metadata-direction agreement and ambiguity only, **not** test model performance.", ""]
        for det,arc in ((p.upstream_detector,p.from_arc),(p.downstream_detector,p.to_arc)):
            m=matches.loc[matches.detector_id.eq(det)&matches.arc_id.eq(arc)]
            if len(m)!=1:raise ValueError(f"Ambiguous/missing source evidence for {det}/{arc}")
            r=m.iloc[0]
            fields += [f"## {det}: authentic metadata and candidate route", "",
                f"- Detector description: {r.detector_description}; source metadata direction: {r.metadata_direction}; observed direction: {r.direction}; agree: {r.metadata_direction_agrees}.",
                f"- Road: `{r.road_name}` route `{r.route_id}` arc `{r.arc_id}`, source direction code `{r.travel_direction}` grade `{r.elevation}`; last road update `{r.road_source_last_updated}` (not historical proof).",
                f"- EPSG:2326 point ({r.easting}, {r.northing}); actual point-to-polyline {r.distance_m:.2f} m; local tangent error {r.directional_error_deg:.1f}°; name check `{r.name_evidence}`; parallel/grade risk `{r.parallel_or_grade_risk}`.",
                f"- Other plausible carriageways/grade-separated alternatives: [all candidates](mapping_candidates96.parquet); human review required.", ""]
        fields += ["## Source INTERSECTION and TURN evidence", "",
            f"- Original INTERSECTION records: [ranked_pair_intersections.csv](ranked_pair_intersections.csv); TURN records touching reviewed routes: [ranked_pair_turns.csv](ranked_pair_turns.csv).",
            "- Source endpoint continuity and intersection membership do **not** prove legal movements; negative NO_TURN restrictions blocked, conditional/fractional restrictions and absence-of-prohibition require human check.", "",
            "## Historical and measurement review gate (leave blank until independent approval)", "",
            "- [ ] Identify both physical lanes, parallel carriageways, bridges/tunnels and source elevation code meanings.",
            "- [ ] Confirm path arc direction, endpoint/intersection membership, TURN movement conditions and relevant traffic regulations.",
            "- [ ] Obtain 2023–September 2026 effective network versions, changes, and detector install/retirement evidence; `irn_version=20221210` is NOT reconciled to October 2026 CENTERLINE.",
            "- [ ] Confirm neighbor lane measurement independence and as-of archive replay semantics; do not fit on candidate-level opportunity data.",
            "- Reviewer identity: ______  Decision: ______  Evidence URLs/SHA-256: ______  Historical [valid_from, valid_to): ______", "",
            "## Original network source SHA-256 / timestamps", ""]
        for name in ("CENTERLINE.gml","INTERSECTION.gml","TURN.gml"):
            src=roads[name]
            fields += [f"- `{name}`: {src['url']}; SHA-256 `{src['sha256']}`; retrieved `{src['http_metadata']['retrieved_at']}`; HTTP Last-Modified `{src['http_metadata']['headers'].get('last-modified','not supplied')}`."]
        fields += ["- Detector metadata SHA-256: `f30818ec94984c024f0188e2e45139ac684c4636aae7906561e227f01407423d`; source metadata historical date unspecified.", ""]
        files[i+1].write_text("\n".join(fields),encoding="utf-8")
    outputs={p.name:sha256_file(p) for p in files[:-1]}
    outputs["ranked_pair_selection.csv"]=sha256_file(report/"ranked_pair_selection.csv")
    outputs["ranked_directional_map_manifest.json"]=sha256_file(report/"ranked_directional_map_manifest.json")
    files[-1].write_text(json.dumps({"status":"review_pending_no_human_approval","sha256":outputs},indent=2)+"\n",encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    parser.add_argument("--network",type=Path,default=Path("data/local/network-full/v1"))
    a=parser.parse_args();run(a.report,a.network)

if __name__=="__main__":main()
