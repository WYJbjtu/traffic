"""96-lane official-geometry candidate evidence; never grants historical approval.

Discovery: 50 m point/line, 45 degree tangent, 10 m ambiguity margin;
1,000 m directed network path and at most five arcs. All are exploratory
search limits, never traffic-propagation parameters or verified routing.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pyproj import Transformer
from shapely import from_wkb
from shapely.geometry import LineString, Point, mapping
from shapely.strtree import STRtree

from traffic_recovery.data.http import sha256_file
from traffic_recovery.network.feasibility import name_evidence
from traffic_recovery.network.pilot import COMPASS, match_candidates

ZIP_SHA = "f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8"
RADIUS_M, BEARING_DEG, MAX_PATH_M, MAX_ARCS = 50, 45, 1000, 5
UNIT = ["detector_id", "direction", "lane_id"]


def verify_release(archive: Path, extracted: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Verify ZIP and all 23 member SHA256s using extracted large Parquet bytes.

    Reads smaller members directly from ZIP; never expands the 860 MB bins member
    into memory. The extracted events/bins/metadata must match the ZIP manifest.
    """
    if sha256_file(archive) != ZIP_SHA:
        raise ValueError("Wrong expanded96 Release ZIP bytes")
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read("SHARED_DATA_MANIFEST.json"))
        if manifest["units"] != 96 or manifest["events"] != 30452:
            raise ValueError("Wrong Release cohort identity")
        for name, record in manifest["files"].items():
            path = extracted / name
            if path.is_file():
                if path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
                    raise ValueError(f"Extracted Release file changed: {name}")
            else:
                # Read each of the small members in bounded chunks, without
                # modifying the existing local extraction or artifacts.
                if record["bytes"] > 5_000_000:
                    raise FileNotFoundError(f"Large Release input not extracted: {path}")
                h = hashlib.sha256()
                with z.open(name) as stream:
                    while data := stream.read(1024 * 1024):
                        h.update(data)
                if h.hexdigest() != record["sha256"]:
                    raise ValueError(f"ZIP member SHA256 differs: {name}")
        inventory = json.loads(z.read("reports/pilot_manifest.json"))
        units = pd.DataFrame([item["unit"] for item in inventory["per_unit"]])
    if len(units) != 96 or units.duplicated(UNIT).any():
        raise ValueError("Frozen lane unit inventory invalid")
    events = pd.read_parquet(extracted / "processed/events.parquet")
    if (len(events) != 30452 or events.event_id.duplicated().any() or
            events.split_proposal.value_counts().to_dict() != {"train": 14290, "validation": 8557, "test": 7605} or
            events[UNIT].drop_duplicates().shape[0] != 94 or
            not set(map(tuple, events[UNIT].to_numpy())).issubset(set(map(tuple, units[UNIT].to_numpy())))):
        raise ValueError("Expanded96 events/splits/lane identities differ")
    bins = pq.ParquetFile(extracted / "processed/cohort_bins.parquet")
    if bins.metadata.num_rows != 35782769:
        raise ValueError("Expanded96 five-minute bin count differs")
    return units, events, manifest


def verify_network(folder: Path) -> dict:
    """Authenticate existing SQLite and official source files; do not download/rebuild."""
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["source_segments"], manifest["directed_arcs"], manifest["crs_source"]) != (36525, 48080, "EPSG:2326"):
        raise ValueError("Unexpected official network counts or CRS")
    db = sqlite3.connect(folder / "topology_index.sqlite")
    try:
        if db.execute("SELECT count(*) FROM roads").fetchone()[0] != 36525 or db.execute("SELECT count(*) FROM arcs").fetchone()[0] != 48080:
            raise ValueError("Network topology index count mismatch")
    finally:
        db.close()
    for source in manifest["sources"].values():
        # Manifest paths are repo-relative, never silently resolve from user's home.
        path = Path(source["path"])
        if not path.is_file() or sha256_file(path) != source["sha256"]:
            raise ValueError(f"Official source hash mismatch: {path}")
    return manifest


def geometry_near(folder: Path, points: list[Point], *, radius_m: float = RADIUS_M) -> tuple[list[dict], list[LineString]]:
    """Load only source centroid tiles within 6 km of a detector; 5.2 km max route.

    The source's actual maximum length is checked, so long routes cannot silently
    vanish outside this spatial halo. STRtree then does exact EPSG:2326 distance.
    """
    tile_size, halo = 4000, 6000
    tiles = {f"{x}_{y}" for p in points
             for x in range(int((p.x - halo)//tile_size), int((p.x + halo)//tile_size) + 1)
             for y in range(int((p.y - halo)//tile_size), int((p.y + halo)//tile_size) + 1)}
    all_paths = sorted((folder / "geometry").glob("tile=*/*.parquet"))
    if not all_paths or max(max(pq.read_table(p, columns=["length_m"]).column(0).to_pylist()) for p in all_paths) > halo - radius_m:
        raise ValueError("Network road length exceeds spatial tile halo")
    paths = [p for p in all_paths if p.parent.name.removeprefix("tile=") in tiles]
    attrs, lines = [], []
    for path in paths:
        for row in pq.read_table(path, columns=["route_id", "source_attributes_json", "length_m", "geometry_wkb_2326"]).to_pylist():
            if row["length_m"] > halo - radius_m:
                raise ValueError("Road length exceeds candidate tile halo; enlarge bounded search")
            line = from_wkb(row["geometry_wkb_2326"])
            if any(line.distance(point) <= radius_m for point in points):
                attrs.append(json.loads(row["source_attributes_json"]))
                lines.append(line)
    if not lines or len({a["ROUTE_ID"] for a in attrs}) != len(attrs):
        raise ValueError("No local official routes or duplicate source route")
    return attrs, lines


def match_units(units: pd.DataFrame, metadata: pd.DataFrame, attrs: list[dict],
                lines: list[LineString], *, version: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep every nearby route, even wrong-direction or ambiguous alternatives."""
    if units.duplicated(UNIT).any() or metadata.AID_ID_Number.duplicated().any():
        raise ValueError("Duplicate frozen lane/metadata identity")
    selected = units.merge(metadata, left_on="detector_id", right_on="AID_ID_Number", how="left", validate="many_to_one")
    tree = STRtree(lines)
    candidates, summaries = [], []
    for row in selected.itertuples(index=False):
        p = Point(row.Easting, row.Northing) if pd.notna(row.Easting) and pd.notna(row.Northing) else None
        nearby = match_candidates(p, row.direction, attrs, lines, tree) if p else []
        plausible = [c for c in nearby if c["direction_compatible"]]
        nearest = min((c["distance_m"] for c in plausible), default=np.nan)
        ambiguous = sum(c["distance_m"] <= nearest + 10 for c in plausible) > 1
        base = dict(detector_id=row.detector_id, direction=row.direction, lane_id=row.lane_id,
            detector_description=row.Road_EN, metadata_direction=row.Direction,
            metadata_direction_agrees=row.Direction == row.direction, metadata_source_date="not_provided_in_detector_csv",
            easting=float(row.Easting) if p else np.nan, northing=float(row.Northing) if p else np.nan)
        summaries.append(dict(**base, nearby_count=len(nearby), plausible_count=len(plausible),
            candidate_matched=bool(plausible), ambiguous=ambiguous,
            direction_conflict=bool(nearby and not plausible) or not base["metadata_direction_agrees"],
            review_status="candidate_only_not_human_verified" if plausible else "unmatched",
            mismatch_reason="missing_coordinates" if not p else "direction" if nearby and not plausible else "distance" if not nearby else ""))
        for c in nearby:
            name = name_evidence(str(row.Road_EN), c["road_name"])
            candidates.append(dict(**base, route_id=c["route_id"], arc_id=c["route_id"] + (":F" if c["orientation"] == "forward" else ":R"),
                distance_m=float(c["distance_m"]), directional_error_deg=float(c["direction_difference_deg"]),
                digitised_bearing_deg=c["digitised_bearing_deg"], road_name=c["road_name"],
                travel_direction=c["travel_direction"], orientation=c["orientation"], elevation=c["elevation"],
                direction_compatible=c["direction_compatible"], name_evidence=name,
                ambiguous=ambiguous, parallel_or_grade_risk=ambiguous or c["elevation"] != "0",
                road_source_version=version, road_source_last_updated=attrs[next(i for i, a in enumerate(attrs) if a["ROUTE_ID"] == c["route_id"])].get("LAST_UPD_DATE_V", ""),
                review_status="candidate_only_not_human_verified",
                evidence_reference="official_centerline_sha256;official_detector_metadata_sha256"))
    return pd.DataFrame(candidates), pd.DataFrame(summaries)


def directed_paths(db: sqlite3.Connection, candidates: pd.DataFrame, lines: dict[str, LineString],
                   *, max_distance: float = MAX_PATH_M, max_arcs: int = MAX_ARCS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Enumerate bounded candidate paths; reject restricted U-turns and loops.

    Same-arc travel uses ordered projections. All cross-route movements remain
    unapproved even where INTERSECTION tags exist; absence of TURN is not legality.
    """
    if max_distance <= 0 or max_arcs < 1:
        raise ValueError("Positive discovery limits required")
    valid = candidates.loc[candidates.direction_compatible].copy()
    arc_rows = {r[0]: r for r in db.execute("SELECT arc,route,from_node,to_node,tile,length_m FROM arcs")}
    by_arc = defaultdict(list)
    for c in valid.itertuples(index=False):
        line = lines[c.route_id]
        pos = line.project(Point(c.easting, c.northing))
        if c.orientation == "reverse": pos = line.length - pos
        by_arc[c.arc_id].append((c.detector_id, c.direction, c.lane_id, float(pos)))
    links_cache = {}
    rejected = []
    paths = []
    for origin_arc, starts in by_arc.items():
        for detector, direction, lane, start_pos in starts:
            # Beam is not trimmed by downstream outcome/model performance.
            stack = [(origin_arc, (origin_arc,), 0.0, (), (), start_pos)]
            examined = 0
            while stack:
                arc, sequence, distance_to_start, intersections, nodes, origin_pos = stack.pop()
                examined += 1
                if examined > 50000:
                    raise ValueError("Candidate path search exceeded fixed per-source budget")
                current = arc_rows[arc]
                for other, other_direction, other_lane, position in by_arc.get(arc, ()):
                    if other == detector or (len(sequence) == 1 and position <= origin_pos):
                        continue
                    length = distance_to_start + position - (origin_pos if len(sequence) == 1 else 0)
                    if length < 0 or length > max_distance:
                        continue
                    paths.append(dict(upstream_detector=detector, upstream_direction=direction, upstream_lane=lane,
                        downstream_detector=other, downstream_direction=other_direction, downstream_lane=other_lane,
                        from_arc=origin_arc, to_arc=arc, arc_sequence="|".join(sequence),
                        route_sequence="|".join(a.rsplit(":",1)[0] for a in sequence),
                        node_sequence="|".join(nodes), path_distance_m=length, arc_count=len(sequence),
                        intersection_ids="|".join(i for i in intersections if i),
                        connection_status="CANDIDATE_ONLY_NOT_MODEL_APPROVED",
                        historical_status="historical_network_version_unverified", reviewer=""))
                if len(sequence) >= max_arcs: continue
                if arc not in links_cache:
                    outgoing = db.execute("SELECT arc,route,from_node,to_node,tile,length_m FROM arcs WHERE from_node=?", (current[3],)).fetchall()
                    links_cache[arc] = []
                    for following in outgoing:
                        restrictions = [r[0] for r in db.execute("SELECT turn_id FROM restrictions WHERE from_route=? AND to_route=?", (current[1], following[1]))]
                        if restrictions or following[1] == current[1]:
                            rejected.append(dict(from_arc=arc, to_arc=following[0], node=current[3],
                                reason="restricted_turn" if restrictions else "u_turn_unverified", turn_ids="|".join(restrictions)))
                            continue
                        ints = [r[0] for r in db.execute("""SELECT DISTINCT i.int_id FROM intersection_routes i
                            JOIN intersection_routes j ON i.int_id=j.int_id AND i.node=j.node
                            WHERE i.route=? AND j.route=? AND i.node=?""", (current[1],following[1],current[3]))]
                        links_cache[arc].append((following, ints))
                for following, ints in links_cache[arc]:
                    if following[0] in sequence: continue
                    # Distance on the origin arc from the detector, then full
                    # intermediary arcs, then target projection above.
                    next_distance = distance_to_start + current[5] - (origin_pos if len(sequence) == 1 else 0)
                    if next_distance > max_distance: continue
                    stack.append((following[0], sequence + (following[0],), next_distance,
                                  intersections + (",".join(ints),), nodes + (current[3],), origin_pos))
    return pd.DataFrame(paths), pd.DataFrame(rejected).drop_duplicates()


def detector_geojson(summary: pd.DataFrame) -> dict:
    """Official metadata grid coordinates transformed only for display."""
    transform = Transformer.from_crs(2326, 4326, always_xy=True)
    features = []
    for r in summary.drop_duplicates("detector_id").itertuples(index=False):
        if np.isnan(r.easting) or np.isnan(r.northing): continue
        lon, lat = transform.transform(r.easting, r.northing)
        features.append({"type": "Feature", "geometry": mapping(Point(lon,lat)), "properties": {
            "detector_id":r.detector_id, "source_easting":r.easting,"source_northing":r.northing,
            "coordinate_source":"official_detector_metadata_HK1980_grid",
            "wgs84_export_status":"derived_for_display_datum_under_review"}})
    return {"type":"FeatureCollection","features":features}
