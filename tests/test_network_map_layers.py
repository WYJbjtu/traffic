"""Synthetic offline tile loader check; real map/browser status reported separately."""
import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import LineString

from traffic_recovery.network.map_layers import available_tiles, load_tile


def test_tile_only_and_missing_speed(tmp_path):
    root = tmp_path / "network"
    for tile, rid in [("1_1", "001"), ("2_1", "002")]:
        folder = root / "geometry" / f"tile={tile}"
        folder.mkdir(parents=True)
        line = LineString([(114, 22), (114.001, 22.001)])
        pq.write_table(pa.Table.from_pylist([{"route_id": rid, "geometry_wkb_4326": line.wkb,
            "west": 114., "south": 22., "east": 114.001, "north": 22.001}]), folder / "part.parquet")
    (root / "manifest.json").write_text(json.dumps({"segments_by_4km_hk1980_tile": {"1_1": 1, "2_1": 1}}))
    speed = tmp_path / "snapshot.parquet"
    pd.DataFrame({"segment_id": ["001", "002"], "speed_kmh": [23., 50.], "valid": ["Y", "N"],
        "id_match": [True, True], "irn_version": ["20221210"]*2,
        "observed_at": pd.to_datetime(["2023-01-01T12:00:00+08:00"]*2)}).to_parquet(speed)
    assert available_tiles(root) == ["1_1", "2_1"]
    first = load_tile(root, "1_1", speed)
    assert list(first.route_id) == ["001"] and first.iloc[0].speed_kmh == 23
    assert "unverified" in first.iloc[0].speed_status
    second = load_tile(root, "2_1", speed)
    assert pd.isna(second.iloc[0].speed_kmh)
    assert second.iloc[0].speed_status == "unavailable"
