"""Audit two authentic official processed snapshots against candidate96 route IDs.

ID overlap is NOT historical network compatibility or measurement independence.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from traffic_recovery.data.http import sha256_file


def run(report:Path,processed:Path) -> None:
    """Create a fresh bounded source comparison, never model-approved speeds."""
    output=report/"processed_candidate_route_overlap.csv"
    manifest=report/"processed_candidate_route_overlap_manifest.json"
    if output.exists() or manifest.exists():raise FileExistsError("Refusing overwrite processed source audit")
    pairs=pd.read_csv(report/"candidate_directed_pairs.csv")
    routes=set(pairs.route_sequence.str.split("|").explode())
    rows=[]
    for stamp in ("20230515-1200","20260915-1200"):
        file=processed/f"observations_{stamp}.parquet"
        sample=pd.read_parquet(file)
        xml=processed/"http"/f"segment_{stamp}.xml"
        if sample.source_hash.nunique()!=1 or sample.source_hash.iloc[0]!=sha256_file(xml):
            raise ValueError("Original XML provenance changed")
        eligible=sample.loc[sample.source_valid & sample.speed_kmh.notna()]
        overlap=eligible.loc[eligible.segment_id.isin(routes)]
        if sample.irn_version.nunique()!=1 or sample.irn_version.iloc[0]!="20221210":raise ValueError("Unexpected IRN version")
        rows.append(dict(snapshot=stamp,source_xml_sha256=sha256_file(xml),source_parquet_sha256=sha256_file(file),
            road_version=sample.irn_version.iloc[0],valid_numeric_segments=len(eligible),
            candidate_path_route_ids_with_valid_speed=overlap.segment_id.nunique(),
            version_compatible_segments=int(overlap.network_compatible.sum()),
            model_approved_segments=int(overlap.usable_for_historical_features.sum()),
            raw_processed_independence="not_verified",source_availability_policy="archive_capture_proxy_not_producer_publication"))
    pd.DataFrame(rows).to_csv(output,index=False)
    manifest.write_text(json.dumps({"status":"source_id_overlap_only_not_model_approved",
        "processed_candidate_route_overlap_sha256":sha256_file(output)},indent=2)+"\n",encoding="utf-8")


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    p.add_argument("--processed",type=Path,default=Path("data/local/processed-pilot/v1"))
    a=p.parse_args();run(a.report,a.processed)

if __name__=="__main__":main()
