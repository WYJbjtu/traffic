"""Official archived processed road-segment speed: source-preserving bounded pilot.

A download/retrieval timestamp is NOT historic publication time. An archive
capture timestamp is only an upper-bound proxy, not proof of public availability;
therefore ingestion defaults to unavailable for model features until an explicit
availability policy and compatible historical network are approved.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path

import pandas as pd

from traffic_recovery.data.http import EvidenceClient, sha256_file
from traffic_recovery.data.sources import SEGMENTS, archive_url, list_versions
from traffic_recovery.data.traffic import SchemaError, clean_traffic, parse_traffic


def parse_snapshot(path: Path, *, archive_time: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Parse preserved XML and metadata; quarantine conflicting keys, retain invalid rows.

    `archive_time` is the historical archive version YYYYMMDD-HHMM (GMT+8),
    **not** the source XML observed_at. Without it, available_at remains NaT.
    Even with it the ingestion_status stays version/availability unapproved.
    """
    meta_path = path.with_name(path.name + ".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    digest = sha256_file(path)
    if meta.get("sha256") != digest or meta.get("status") != 200:
        raise ValueError(f"Source evidence mismatch: {path}")
    frame = parse_traffic(path.read_bytes())
    if "segment_id" not in frame:
        raise SchemaError("Not a processed segment-speed XML")
    if frame.irn_version.nunique() != 1:
        raise SchemaError("Multiple IRN versions in snapshot")
    cleaned, quality = clean_traffic(frame, conflicts="quarantine")
    if archive_time is not None:
        capture = pd.Timestamp(datetime.strptime(archive_time, "%Y%m%d-%H%M")).tz_localize("Asia/Hong_Kong")
        if (capture < cleaned.timestamp).any():
            raise ValueError("Archive capture precedes source observation")
    else:
        capture = pd.NaT
    cleaned = cleaned.rename(columns={"timestamp": "observed_at"})
    cleaned["available_at"] = capture  # upper-bound proxy ONLY; not verified publication
    cleaned["source_type"] = "official_processed_segment"
    cleaned["source_url"] = SEGMENTS
    cleaned["source_snapshot_id"] = archive_time or "unversioned_live_sample"
    cleaned["source_hash"] = digest
    cleaned["retrieved_at"] = pd.Timestamp(meta["retrieved_at"]).tz_convert("Asia/Hong_Kong")
    cleaned["ingestion_status"] = "historical_network_and_availability_unverified"
    return cleaned, quality


def exact_join(snapshot: pd.DataFrame, roads: Path) -> tuple[pd.DataFrame, dict]:
    """Exact ROUTE_ID join to network geometry; flags version mismatch, never approves.

    Source strings are not coerced to integers. The network snapshot is from
    October 2026; an earlier IRN version cannot establish geometry compatibility.
    Returns all processed records (including invalid), with nullable road match.
    """
    import pyarrow.dataset as ds
    if not (roads / "manifest.json").exists():
        raise FileNotFoundError(roads / "manifest.json")
    network = json.loads((roads / "manifest.json").read_text(encoding="utf-8"))
    routes = ds.dataset(roads / "geometry", format="parquet", partitioning="hive").to_table(
        columns=["route_id", "travel_direction", "elevation"]).to_pandas()
    if routes.route_id.duplicated().any():
        raise ValueError("Duplicate CENTERLINE ROUTE_ID")
    result = snapshot.merge(routes.rename(columns={"route_id": "segment_id"}),
                            on="segment_id", how="left", validate="many_to_one", indicator=True)
    result["id_match"] = result["_merge"].eq("both")
    result = result.drop(columns=["_merge"])
    result["network_compatible"] = False  # requires historical network/version evidence
    result["usable_for_historical_features"] = False
    report = {"snapshot_rows": len(result), "distinct_segment_ids": int(result.segment_id.nunique()),
        "valid_numeric_rows": int(result.speed_kmh.notna().sum()),
        "valid_numeric_unique_ids": int(result.loc[result.speed_kmh.notna(), "segment_id"].nunique()),
        "exact_id_matches": int(result.id_match.sum()),
        "valid_numeric_exact_matches": int((result.id_match & result.speed_kmh.notna()).sum()),
        "distinct_valid_numeric_matched_ids": int(result.loc[result.id_match & result.speed_kmh.notna(), "segment_id"].nunique()),
        "network_source_sha256": network["sources"]["CENTERLINE.gml"]["sha256"],
        "network_snapshot_status": "October 2026 static snapshot; historical IRN compatibility unverified",
        "approved_historical_features": 0}
    return result, report


def pilot(output: Path, roads: Path, *, dates: tuple[date, ...] = (date(2023, 5, 15), date(2026, 9, 15))) -> dict:
    """Bounded official archive discovery and <=1 snapshot per representative day.

    Stores request/response/bytes/hash using EvidenceClient. Failure on one day
    is explicit in the report and does not masquerade as zero coverage.
    Resume by checksum-verified exact URL reuse; each day has <10k versions.
    """
    client = EvidenceClient(output / "http", timeout=30, attempts=2, reuse=True)
    results = []
    for day in dates:
        key = day.strftime("%Y%m%d")
        entry: dict = {"requested_day_hkt": day.isoformat()}
        try:
            inventory = list_versions(client, SEGMENTS, day, day, f"versions_{key}.json")
            versions = inventory["timestamps"]
            entry["archive_version_count"] = len(versions)
            entry["listing_sha256"] = sha256_file(client.root / f"versions_{key}.json")
            entry["listing_url"] = archive_url("list-file-versions", url=SEGMENTS, start=key, end=key)
            if not versions:
                entry["status"] = "no_archived_versions"
            else:
                selected = versions[len(versions) // 2]
                name = f"segment_{selected}.xml"
                url = archive_url("get-file", url=SEGMENTS, time=selected)
                path = client.fetch(url, name)
                frame, quality = parse_snapshot(path, archive_time=selected)
                joined, coverage = exact_join(frame, roads)
                joined.to_parquet(output / f"observations_{selected}.parquet", index=False)
                entry.update(status="sample_parsed_unapproved", capture_time_hkt=selected,
                             observed_times_hkt=sorted(str(x) for x in frame.observed_at.unique()),
                             irn_versions=sorted(frame.irn_version.unique().tolist()),
                             source_url=SEGMENTS, request_url=url, sha256=sha256_file(path),
                             bytes=path.stat().st_size, retrieved_at_utc=json.loads(
                                 path.with_name(path.name + ".meta.json").read_text(encoding="utf-8"))["retrieved_at"],
                             quality=quality, coverage=coverage)
        except (OSError, ValueError, RuntimeError, SchemaError) as exc:
            entry.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        results.append(entry)
        output.mkdir(parents=True, exist_ok=True)
        (output / "pilot.json").write_text(json.dumps({"results": results,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "warning": "Archive capture is not proven publication time; network version unverified; no model-ready features"},
            indent=2) + "\n", encoding="utf-8")
    return {"results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/local/processed-pilot/v1"))
    parser.add_argument("--roads", type=Path, default=Path("data/local/network-full/v1"))
    parser.add_argument("--dates", type=date.fromisoformat, nargs="+", default=[date(2023, 5, 15), date(2026, 9, 15)])
    args = parser.parse_args()
    print(json.dumps(pilot(args.output, args.roads, dates=tuple(args.dates)), indent=2))


if __name__ == "__main__":
    main()
