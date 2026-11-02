"""Fail-closed coverage report from local official network and bounded archive pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def coverage(network: Path, pilot: Path, archive_catalog: Path, cohort: Path) -> dict:
    """Report observed ID overlap separately from approved time-valid features.

    Catalog months are *inventory listings*, not observed speed coverage. Missing
    long-window event data means event/fold coverage is null, never estimated.
    """
    roads = json.loads((network / "manifest.json").read_text(encoding="utf-8"))
    pilot_report = json.loads((pilot / "pilot.json").read_text(encoding="utf-8"))
    catalog = json.loads(archive_catalog.read_text(encoding="utf-8"))
    inventory = [f for f in catalog["data-files"] if "20230101" <= f["timestamp"] <= "20260930"]
    selected = pd.read_csv(cohort, dtype=str)
    rows = []
    for entry in pilot_report["results"]:
        if entry["status"] != "sample_parsed_unapproved":
            rows.append({"day": entry["requested_day_hkt"], "status": entry["status"]})
            continue
        path = pilot / f"observations_{entry['capture_time_hkt']}.parquet"
        frame = pd.read_parquet(path)
        good = frame.loc[frame.valid.eq("Y") & frame.speed_kmh.notna()]
        by_hour = {str(k): int(v) for k, v in good.groupby(good.observed_at.dt.hour).size().items()}
        rows.append({"day": entry["requested_day_hkt"], "capture_hkt": entry["capture_time_hkt"],
            "observed_hkt": entry["observed_times_hkt"], "archive_versions_that_day": entry["archive_version_count"],
            "raw_segments_with_valid_speed": len(good), "valid_speed_by_hour_hkt": by_hour,
            "exact_id_matches_valid": entry["coverage"]["valid_numeric_exact_matches"],
            "id_match_pct_of_geometry": round(100*entry["coverage"]["distinct_valid_numeric_matched_ids"] /
                roads["parsed_valid_segments"], 3), "approved_model_ready_pct_of_geometry": 0,
            "irn_version": entry["irn_versions"], "source_hash": entry["sha256"],
            "retrieved_at_utc": entry["retrieved_at_utc"]})
    return {"physical_network_segments": roads["parsed_valid_segments"],
        "physical_network_source_sha256": roads["sources"]["CENTERLINE.gml"]["sha256"],
        "archive_catalog_source": str(archive_catalog),
        "archive_catalog_months_or_daily_entries_2023_through_sep2026": len(inventory),
        "archive_inventory_by_year": {str(year): len([v for v in inventory if v["timestamp"].startswith(str(year))])
                                      for year in range(2023, 2027)},
        "historical_coverage_by_month": "not measured; inventory presence is not per-segment speed coverage",
        "sampled_speed_coverage": rows, "sampled_time_of_day_hours_only": sorted({h for row in rows for h in row.get("valid_speed_by_hour_hkt", {})}),
        "long_window_cohort_detector_count": selected.detector_id.nunique(),
        "long_window_event_coverage_by_fold": None,
        "upstream_usable_events": None, "downstream_usable_events": None,
        "both_usable_events": None, "processed_supplements_missing_raw_neighbors": None,
        "events_with_no_spatial_observation": None,
        "version_incompatible_or_unverified_events": None,
        "reason_event_metrics_missing": "Prepared long-window events/bins absent locally; mapping and graph unverified; processed publication time unknown",
        "scientific_status": "NO-GO; ID overlap is not historical network compatibility or independent observation"}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--network", type=Path, default=Path("data/local/network-full/v1"))
    p.add_argument("--pilot", type=Path, default=Path("data/local/processed-pilot/v1"))
    p.add_argument("--catalog", type=Path, default=Path("data/local/smoke-audit/coverage_segment.json"))
    p.add_argument("--cohort", type=Path, default=Path("reports/long_window/cohort.csv"))
    p.add_argument("--output", type=Path, default=Path("data/local/processed-pilot/coverage.json"))
    args = p.parse_args()
    report = coverage(args.network, args.pilot, args.catalog, args.cohort)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
