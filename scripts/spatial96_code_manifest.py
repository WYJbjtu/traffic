"""Bind executed spatial96 code, dependencies and generated artifact hashes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from traffic_recovery.data.http import sha256_file

ROOT=Path(__file__).resolve().parents[1]
CODE=["src/traffic_recovery/network/spatial96.py",
      "src/traffic_recovery/network/spatial96_coverage.py",
      "scripts/spatial96.py","scripts/spatial96_review.py","scripts/spatial96_enrichment.py",
      "scripts/spatial96_direction_maps.py","scripts/spatial96_ranked_packet.py",
      "scripts/spatial96_processed_overlap.py","scripts/spatial96_code_manifest.py",
      "tests/test_network_spatial96.py",
      "src/traffic_recovery/network/pilot.py","src/traffic_recovery/network/feasibility.py",
      "src/traffic_recovery/network/full_network.py","src/traffic_recovery/network/spatial_features.py",
      "uv.lock"]

def run(report:Path,local:Path) -> None:
    """Refuse replacement; list all present report/local files and code SHA256."""
    path=report/"reproduction_manifest.json"
    if path.exists():raise FileExistsError(path)
    manifest={"approval":"NO-GO;candidate_observations_not_admissible_as_spatial_model_features",
        "code_sha256":{name:sha256_file(ROOT/name) for name in CODE},
        "report_outputs_sha256":{p.name:sha256_file(p) for p in sorted(report.iterdir()) if p.is_file()},
        "local_outputs_sha256":{p.name:sha256_file(p) for p in sorted(local.iterdir()) if p.is_file()}}
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,default=Path("reports/spatial96_nov05"))
    parser.add_argument("--local",type=Path,default=Path("data/local/spatial96/v1"))
    a=parser.parse_args();run(a.report,a.local)

if __name__=="__main__":main()
