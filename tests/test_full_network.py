"""Synthetic source-like CityGML: topology behavior, never empirical counts."""
import json
from pathlib import Path

import pyarrow.dataset as ds
import pytest
from shapely import wkb

from traffic_recovery.network.full_network import arc_endpoints, build_network


def gml(path: Path, records: list[tuple[dict, str]]) -> None:
    objects = []
    for attrs, geometry in records:
        fields = "".join(f'<gen:stringAttribute name="{k}"><gen:value>{v}</gen:value></gen:stringAttribute>'
                         for k, v in attrs.items())
        objects.append(f"<core:cityObjectMember><gen:GenericCityObject>{fields}{geometry}</gen:GenericCityObject></core:cityObjectMember>")
    path.write_text('<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0" '
                    'xmlns:gen="http://www.opengis.net/citygml/generics/2.0" '
                    'xmlns:gml="http://www.opengis.net/gml">' + "".join(objects) +
                    "</core:CityModel>", encoding="utf-8")


def line(points: str) -> str:
    return f'<gml:LineString srsName="EPSG:2326"><gml:posList>{points}</gml:posList></gml:LineString>'


def point(x: float, y: float) -> str:
    return f'<gml:Point srsName="EPSG:2326"><gml:pos>{x} {y}</gml:pos></gml:Point>'


def test_full_network_grade_turn_and_geographic_geometry(tmp_path):
    roads, intersections, turns = [tmp_path / f"{part}.gml" for part in ("roads", "ints", "turns")]
    x, y = 835000, 815000
    gml(roads, [
        ({"ROUTE_ID": "001", "TRAVEL_DIRECTION": "3", "ELEVATION": "0"}, line(f"{x} {y} {x+10} {y}")),
        ({"ROUTE_ID": "002", "TRAVEL_DIRECTION": "1", "ELEVATION": "0"}, line(f"{x+10} {y} {x+20} {y}")),
        ({"ROUTE_ID": "003", "TRAVEL_DIRECTION": "3", "ELEVATION": "1"}, line(f"{x+10} {y-10} {x+10} {y+10}")),
        ({"ROUTE_ID": "004", "TRAVEL_DIRECTION": "3", "ELEVATION": "0"}, line(f"{x+5} {y-10} {x+5} {y+10}")),
    ])
    gml(intersections, [({"INT_ID": "I", "RD_ID_1": "001", "RD_ID_2": "002"}, point(x+10, y))])
    gml(turns, [({"TURN_ID": "T", "NO_TURN": "-1", "EDGE1FID": "001", "EDGE2FID": "002"}, "")])
    report = build_network(roads, intersections, turns, tmp_path / "out", batch_size=2)
    assert (report["source_segments"], report["parsed_valid_segments"], report["directed_arcs"]) == (4, 4, 5)
    assert report["transition_status_counts"]["turn_restricted"] >= 1
    assert report["weak_endpoint_components"] == 3  # no crossing at interior or different grade
    geo = ds.dataset(tmp_path / "out/geometry", format="parquet", partitioning="hive").to_table().to_pandas()
    assert set(geo.route_id) == {"001", "002", "003", "004"}
    assert 113 < wkb.loads(geo.iloc[0].geometry_wkb_4326).coords[0][0] < 115
    transitions = ds.dataset(tmp_path / "out/transitions", format="parquet", partitioning="hive").to_table().to_pandas()
    assert not ((transitions.from_route == "003") & (transitions.to_route == "002")).any()
    assert not ((transitions.from_route == "004") & (transitions.to_route == "001")).any()
    row = transitions.loc[(transitions.from_route == "001") & (transitions.to_route == "002")].iloc[0]
    assert row.status == "turn_restricted" and row.restricting_turn_ids == "T"
    assert json.loads((tmp_path / "out/manifest.json").read_text())["topology_status"].startswith("unverified")


def test_direction_and_duplicate_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        arc_endpoints("1", "2", "0", [(0, 0), (1, 1)])
    with pytest.raises(ValueError, match="output must not exist"):
        build_network(tmp_path / "missing", tmp_path / "missing", tmp_path / "missing", tmp_path)
