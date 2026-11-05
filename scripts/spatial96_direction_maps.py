"""Append original-line, arrowed candidate path maps (no fabricated road links)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from shapely import from_wkb

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from traffic_recovery.data.http import sha256_file


def run(report:Path, network:Path, *, ranked:bool=False) -> dict:
    """Overlay actual directed centerline arcs, source intersections and detectors."""
    pairs=pd.read_csv(report/"candidate_directed_pairs.csv",dtype={"arc_sequence":str,"route_sequence":str})
    if ranked:
        matches=pd.read_parquet(report/"mapping_candidates96.parquet")
        for side,arc_col in (("upstream","from_arc"),("downstream","to_arc")):
            table=matches[["detector_id","arc_id","distance_m","name_evidence","metadata_direction_agrees","ambiguous"]].rename(
                columns={"detector_id":side+"_detector","arc_id":arc_col,
                    **{c:side+"_"+c for c in ("distance_m","name_evidence","metadata_direction_agrees","ambiguous")}})
            pairs=pairs.merge(table,on=[side+"_detector",arc_col],validate="many_to_one")
        pairs=pairs.loc[pairs.intersection_ids.notna()].copy()
        # Predeclared evidentiary ranking; no outcomes or model scores. De-duplicate
        # corridor route sequences so the six review packets are not one road.
        pairs["evidence_score"]=(pairs.upstream_name_evidence.eq("name_in_detector_description").astype(int)
            + pairs.downstream_name_evidence.eq("name_in_detector_description").astype(int))*5
        pairs["evidence_score"] -= (pairs.upstream_distance_m+pairs.downstream_distance_m)/20
        pairs["evidence_score"] -= (pairs.upstream_ambiguous.astype(int)+pairs.downstream_ambiguous.astype(int))*2
        pairs["evidence_score"] -= (~pairs.upstream_metadata_direction_agrees).astype(int)*2 + (~pairs.downstream_metadata_direction_agrees).astype(int)*2
        pairs=pairs.sort_values(["evidence_score","path_distance_m"],ascending=[False,True]).drop_duplicates("route_sequence").head(6)
        target=report/"ranked_pair_selection.csv"
        if target.exists():raise FileExistsError(target)
        pairs.to_csv(target,index=False)
    else: pairs=pairs.loc[pairs.intersection_ids.notna()].head(6)
    routes={r for seq in pairs.route_sequence for r in seq.split("|")}
    import pyarrow.parquet as pq
    shapes={}
    for path in (network/"geometry").glob("tile=*/*.parquet"):
        for row in pq.read_table(path,columns=["route_id","geometry_wkb_2326","elevation","source_attributes_json"]).to_pylist():
            if row["route_id"] in routes:
                shapes[row["route_id"]]=row
    if len(shapes)!=len(routes):raise ValueError("Missing official road path geometry")
    locations=pd.read_csv(report/"mapping_summary.csv").set_index("detector_id")
    ints=pd.read_csv(report/"selected_pair_intersections.csv",dtype={"INT_ID":str})
    # Original GML intersection positions, not assumed from detector proximity.
    from traffic_recovery.network.pilot import read_features
    network_manifest=json.loads((network/"manifest.json").read_text(encoding="utf-8"))
    intersection_ids={i for sequence in pairs.intersection_ids for i in str(sequence).split("|")} if ranked else set(ints.INT_ID)
    official_intersections={}
    for attrs,element in read_features(Path(network_manifest["sources"]["INTERSECTION.gml"]["path"])):
        if attrs.get("INT_ID") not in intersection_ids:continue
        point=element.find(".//{*}Point")
        if point is None or point.get("srsName")!="EPSG:2326":raise ValueError("Unexpected intersection CRS")
        official_intersections[attrs["INT_ID"]]=tuple(map(float,point.findtext("{*}pos","").split()))
    outputs={}
    for i,p in enumerate(pairs.itertuples(),1):
        target=report/(f"ranked-directed-pair-{i}.png" if ranked else f"directed-pair-{i}.png")
        if target.exists():raise FileExistsError(target)
        fig,ax=plt.subplots(figsize=(10,7))
        for arc in p.arc_sequence.split("|"):
            rid,orientation=arc.rsplit(":",1)
            shape=shapes[rid]
            line=from_wkb(shape["geometry_wkb_2326"])
            x,y=line.xy;ax.plot(x,y,lw=2,label=f"{arc} / grade {shape['elevation']}")
            a=line.interpolate(line.length*.35);b=line.interpolate(line.length*.65)
            if orientation=="R": a,b=b,a
            ax.annotate("",(b.x,b.y),(a.x,a.y),arrowprops=dict(arrowstyle="->",lw=2,color="black"))
        for det in (p.upstream_detector,p.downstream_detector):
            row=locations.loc[det];ax.scatter(row.easting,row.northing,c="red",s=35)
            ax.text(row.easting,row.northing,f"{det} {row.direction}",fontsize=8)
        for identifier in str(p.intersection_ids).split("|"):
            if identifier not in official_intersections:raise ValueError("Missing referenced official intersection")
            x,y=official_intersections[identifier]
            ax.scatter(x,y,c="green",marker="x",s=50);ax.text(x,y,"INT "+identifier,fontsize=7)
        ax.set_aspect("equal");ax.legend(fontsize=7,loc="best")
        ax.set(title=f"Official directed path candidate {i} — NOT legal/historical approval",
            xlabel="Easting EPSG:2326 (m)",ylabel="Northing EPSG:2326 (m)")
        fig.tight_layout();fig.savefig(target,dpi=135);plt.close(fig)
        outputs[target.name]=sha256_file(target)
    manifest=report/("ranked_directional_map_manifest.json" if ranked else "directional_map_manifest.json")
    if manifest.exists():raise FileExistsError(manifest)
    manifest.write_text(json.dumps({"status":"candidate_only","road_source_sha256":network_manifest["sources"]["CENTERLINE.gml"]["sha256"],
        "intersection_source_sha256":network_manifest["sources"]["INTERSECTION.gml"]["sha256"],
        "sha256":outputs},indent=2)+"\n",encoding="utf-8")
    return outputs


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    parser.add_argument("--network",type=Path,default=Path("data/local/network-full/v1"))
    parser.add_argument("--ranked",action="store_true",help="Separate high-evidence candidate packets; no human approval")
    a=parser.parse_args();print(run(a.report,a.network,ranked=a.ranked))

if __name__=="__main__":main()
