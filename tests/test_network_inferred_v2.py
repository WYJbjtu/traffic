"""Synthetic fixtures for inferred research graph, not observed research results."""
import pandas as pd
import sqlite3

from traffic_recovery.network.inferred_v2 import score_mappings, inferred_paths, asof_index, inferred_transitions


def test_mapping_ranks_and_retains_alternatives():
    key = dict(detector_id="A", direction="East", lane_id="1")
    base = dict(**key, metadata_direction_agrees=True, name_evidence="name_in_detector_description",
                elevation="0", direction_compatible=True, directional_error_deg=5)
    rows = [dict(base, arc_id="r:F", distance_m=4), dict(base, arc_id="s:F", distance_m=29),
            dict(base, arc_id="q:R", distance_m=2, direction_compatible=False)]
    ranked = score_mappings(pd.DataFrame(rows), pd.DataFrame([key, dict(key, detector_id="B")]))
    assert len(ranked) == 4
    assert ranked.loc[ranked.arc_id.eq("r:F"), "quality_tier"].iloc[0] == "HIGH_CONFIDENCE_INFERRED"
    assert ranked.loc[ranked.arc_id.eq("q:R"), "quality_tier"].iloc[0] == "DIRECTION_INCOMPATIBLE"
    assert ranked.loc[ranked.detector_id.eq("B"), "quality_tier"].iloc[0] == "UNMATCHED"


def test_unsourced_junction_rejected():
    maps = pd.DataFrame([dict(detector_id=k, direction="East", lane_id="1", arc_id=f"{k}:F",
                              rank=1, quality_tier="HIGH_CONFIDENCE_INFERRED", distance_m=3)
                         for k in ("A", "B")]).set_index(["detector_id", "direction", "lane_id"], drop=False).reset_index(drop=True)
    path = dict(upstream_detector="A", upstream_direction="East", upstream_lane="1",
                downstream_detector="B", downstream_direction="East", downstream_lane="1",
                from_arc="A:F", to_arc="B:F", route_sequence="A|B", arc_sequence="A:F|B:F",
                path_distance_m=50., arc_count=2, intersection_ids="")
    assert inferred_paths(pd.DataFrame([path]), maps, "HIGH_CONFIDENCE_INFERRED").empty
    path["intersection_ids"] = "official-id"
    assert len(inferred_paths(pd.DataFrame([path]), maps, "HIGH_CONFIDENCE_INFERRED")) == 1


def test_graph_requires_same_grade_source_intersection_and_no_turn_prohibition():
    db = sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE arcs(arc TEXT, route TEXT, from_node TEXT, to_node TEXT, length_m REAL);
        CREATE TABLE intersection_routes(route TEXT, node TEXT, int_id TEXT);
        CREATE TABLE restrictions(from_route TEXT, to_route TEXT, turn_id TEXT);
        INSERT INTO arcs VALUES ('A:F','A','x:0','y:0',20),('B:F','B','y:0','z:0',30),
            ('C:F','C','y:1','z:1',10),('D:F','D','y:0','z:0',25);
        INSERT INTO intersection_routes VALUES ('A','y:0','i1'),('B','y:0','i1'),
            ('C','y:1','i1'),('D','y:0','i1');
        INSERT INTO restrictions VALUES ('A','D','turn1');""")
    edges = inferred_transitions(db)
    assert list(zip(edges.from_arc, edges.to_arc)) == [("A:F", "B:F")]


def test_asof_requires_all_three_watermarks_and_age():
    zone = "Asia/Hong_Kong"
    t = pd.Timestamp("2024-01-01 12:00", tz=zone)
    frame = pd.DataFrame({"timestamp": [t - pd.Timedelta(minutes=10), t - pd.Timedelta(minutes=5)],
        "usable": [True, True], "speed_kmh": [30., 40.],
        "available_at": [t, t], "last_source_available_at": [t, t + pd.Timedelta(seconds=1)]})
    assert asof_index(frame, t.value) == 0
    assert asof_index(frame, (t + pd.Timedelta(minutes=16)).value) is None
