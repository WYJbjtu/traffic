"""Synthetic XML only; no empirical coverage claims."""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from traffic_recovery.data.processed_segments import exact_join, parse_snapshot
from traffic_recovery.network.observations import neighbor_speeds


def snapshot(tmp_path: Path, segments: str, *, capture: str = "20230515-1200"):
    path = tmp_path / "archived.xml"
    data = ('<segment_speed_list><date>2023-05-15</date><time>11:54:00</time>'
            '<irn_version>20221210</irn_version><segments>' + segments +
            '</segments></segment_speed_list>').encode()
    path.write_bytes(data)
    (tmp_path / "archived.xml.meta.json").write_text(json.dumps({
        "sha256": hashlib.sha256(data).hexdigest(), "status": 200,
        "retrieved_at": "2026-11-02T08:15:35+00:00"}), encoding="utf-8")
    return parse_snapshot(path, archive_time=capture)


def test_processed_flags_zero_missing_conflicts_and_capture(tmp_path):
    segment = lambda rid, speed, valid: (f"<segment><segment_id>{rid}</segment_id>"
        f"<speed>{speed}</speed><valid>{valid}</valid></segment>")
    frame, quality = snapshot(tmp_path, segment("001", "0", "Y") +
        segment("002", "80", "N") + segment("003", "", "Y") +
        segment("004", "20", "Y") + segment("004", "21", "Y"))
    assert quality["conflicting_keys_quarantined"] == 1
    assert list(frame.segment_id) == ["001", "002", "003"]
    assert frame.iloc[0].speed_kmh == 0
    assert pd.isna(frame.iloc[1].speed_kmh) and pd.isna(frame.iloc[2].speed_kmh)
    assert str(frame.iloc[0].observed_at.tzinfo) == "Asia/Hong_Kong"
    assert frame.iloc[0].available_at > frame.iloc[0].observed_at
    assert not frame.ingestion_status.eq("approved").any()


def test_capture_must_follow_observation(tmp_path):
    with pytest.raises(ValueError, match="capture precedes"):
        snapshot(tmp_path, "<segment><segment_id>1</segment_id><speed>30</speed><valid>Y</valid></segment>",
                 capture="20230515-1153")


def test_exact_ids_never_approve_historical_version(tmp_path):
    frame, _ = snapshot(tmp_path, "<segment><segment_id>001</segment_id><speed>50</speed><valid>Y</valid></segment>"
        "<segment><segment_id>000</segment_id><speed>45</speed><valid>Y</valid></segment>")
    folder = tmp_path / "network/geometry/tile=1_1"
    folder.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([{"route_id": "001", "travel_direction": "3", "elevation": "0"}]),
                   folder / "part.parquet")
    (tmp_path / "network/manifest.json").write_text(json.dumps({
        "sources": {"CENTERLINE.gml": {"sha256": "synthetic"}}}), encoding="utf-8")
    joined, report = exact_join(frame, tmp_path / "network")
    assert joined.set_index("segment_id").loc["001", "id_match"]
    assert not joined.set_index("segment_id").loc["000", "id_match"]
    assert not joined.network_compatible.any() and not joined.usable_for_historical_features.any()
    assert report["approved_historical_features"] == 0


def test_asof_missing_and_raw_precedence_with_provenance():
    tz = "Asia/Hong_Kong"
    when = pd.Timestamp(datetime(2023, 5, 15, 12, tzinfo=__import__("zoneinfo").ZoneInfo(tz)))
    base = {"segment_id": ["1", "2", "3"], "observed_at": pd.to_datetime([when-timedelta(minutes=6),
        when-timedelta(minutes=6), when+timedelta(minutes=1)]),
        "available_at": pd.to_datetime([when-timedelta(minutes=1), when-timedelta(minutes=1),
                                          when+timedelta(minutes=2)]), "speed_kmh": [0., 40., 100.],
        "network_version": ["V"]*3, "review_status": ["human_verified"]*3,
        "source_hash": ["p"]*3}
    processed = pd.DataFrame(base).assign(valid="Y", source_type="official_processed_segment",
                                           usable_for_historical_features=True)
    raw = pd.DataFrame({k: [v[0]] for k, v in base.items()}).assign(speed_kmh=21., source_hash="raw")
    result = neighbor_speeds(["1", "2", "3", "4"], when, processed, raw, network_version="V")
    assert list(result.source_type) == ["raw_detector_observed", "official_processed_segment",
                                       "unavailable", "unavailable"]
    assert result.iloc[0].speed_kmh == 21 and result.iloc[0].processed_speed_kmh == 0
    assert result.iloc[0].possible_source_dependence
    assert pd.isna(result.iloc[2].speed_kmh)
    processed["usable_for_historical_features"] = False
    assert neighbor_speeds(["2"], when, processed, raw, network_version="V").iloc[0].source_type == "unavailable"
    raw["available_at"] = raw["observed_at"] + timedelta(minutes=10)
    assert neighbor_speeds(["1"], when, processed, raw, network_version="V").iloc[0].source_type == "unavailable"
