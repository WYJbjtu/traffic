"""Stream official CENTERLINE into tiled geometry and a separate candidate topology.

All coordinates in topology are EPSG:2326 metres. Endpoint equality (1 cm) is
only a *candidate* connection. INTERSECTION membership provides additional
source evidence, not proof of a legal, historically valid turn. No crossings
are connected without shared endpoints. Large outputs remain local/ignored.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import time

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Transformer
from shapely import transform
from shapely.geometry import LineString

from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.sources import NETWORK_STATIC
from traffic_recovery.network.feasibility import source_coordinates
from traffic_recovery.network.pilot import read_features


def node_key(x: float, y: float, elevation: str) -> str:
    """Source endpoint rounded to centimetres, with exact source grade code."""
    return f"{round(x * 100)}:{round(y * 100)}:{elevation}"


def arc_endpoints(route: str, direction: str, elevation: str,
                  coords: list[tuple[float, float]]) -> list[tuple[str, str, str, str]]:
    """Return (arc_id, route_id, from_node, to_node), or reject unknown direction."""
    if direction not in {"1", "3"}:
        raise ValueError(f"Unsupported TRAVEL_DIRECTION {direction!r}: {route}")
    start, end = node_key(*coords[0], elevation), node_key(*coords[-1], elevation)
    arcs = [(route + ":F", route, start, end)]
    if direction == "1":
        arcs.append((route + ":R", route, end, start))
    return arcs


def _write_batch(root: Path, batch: list[dict], counts: Counter, category: str) -> None:
    """Write one bounded row batch per tile; never accumulate country-wide shapes."""
    tiles: dict[str, list[dict]] = defaultdict(list)
    for row in batch:
        tiles[row.pop("_tile")].append(row)
    for tile, rows in tiles.items():
        folder = root / f"tile={tile}"
        folder.mkdir(parents=True, exist_ok=True)
        number = counts[category, tile]
        counts[category, tile] += 1
        pq.write_table(pa.Table.from_pylist(rows), folder / f"part-{number:05d}.parquet",
                       compression="zstd")


def _components(db: sqlite3.Connection) -> tuple[int, int, int]:
    """Weak endpoint components, ignoring turn legality (not a routing metric)."""
    parent: dict[str, str] = {}
    size: dict[str, int] = {}

    def find(n: str) -> str:
        parent.setdefault(n, n)
        size.setdefault(n, 1)
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for a, b in db.execute("SELECT from_node,to_node FROM arcs"):
        x, y = find(a), find(b)
        if x != y:
            if size[x] < size[y]:
                x, y = y, x
            parent[y] = x
            size[x] += size[y]
    roots = [size[n] for n in parent if parent[n] == n]
    return len(parent), len(roots), max(roots, default=0)


def build_network(centerline: Path, intersections: Path, turns: Path, output: Path,
                  *, batch_size: int = 2048) -> dict:
    """Construct geometry/arc/candidate-transition tiled Parquet and manifest.

    Inputs are local official GML; output must be an unused directory. Errors in
    individual geometry are counted and identified, while duplicate identifiers
    or unknown direction fail closed. SQLite is an ignored on-disk work index.
    Returns counts and provenance; no navigational connectivity is certified.
    """
    if batch_size < 1 or output.exists():
        raise ValueError("batch_size must be positive and output must not exist")
    for path in (centerline, intersections, turns):
        if not path.is_file():
            raise FileNotFoundError(path)
    start = time.monotonic()
    output.mkdir(parents=True)
    db = sqlite3.connect(output / "topology_index.sqlite")
    db.execute("CREATE TABLE roads (route TEXT PRIMARY KEY)")
    db.execute("CREATE TABLE arcs (arc TEXT PRIMARY KEY, route TEXT, from_node TEXT, to_node TEXT, tile TEXT, length_m REAL)")
    db.execute("CREATE INDEX arc_from ON arcs(from_node)")
    db.execute("CREATE INDEX arc_route ON arcs(route)")
    db.execute("CREATE TABLE intersection_routes (route TEXT, node TEXT, int_id TEXT)")
    db.execute("CREATE INDEX intersection_route_node ON intersection_routes(route,node)")
    db.execute("CREATE TABLE restrictions (from_route TEXT, to_route TEXT, turn_id TEXT)")
    db.execute("CREATE INDEX restriction_pair ON restrictions(from_route,to_route)")
    to_wgs = Transformer.from_crs(2326, 4326, always_xy=True).transform
    counts: Counter = Counter()
    invalid: list[dict] = []
    geometry_batch: list[dict] = []
    arc_batch: list[dict] = []
    try:
        for index, (attrs, element) in enumerate(read_features(centerline), 1):
            counts["source_segments"] += 1
            route = attrs.get("ROUTE_ID", "")
            if not route:
                raise ValueError(f"Missing ROUTE_ID at source object {index}")
            try:
                coords = source_coordinates(element)
                line = LineString(coords)
                if not line.is_valid or line.is_empty or line.length <= 0 or not all(
                    math.isfinite(v) for xy in coords for v in xy
                ):
                    raise ValueError("Invalid/zero-length/nonfinite geometry")
                arcs = arc_endpoints(route, attrs.get("TRAVEL_DIRECTION", ""),
                                     attrs.get("ELEVATION", ""), coords)
                wgs = transform(line, to_wgs, interleaved=False)
                west, south, east, north = wgs.bounds
                if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
                    raise ValueError("Invalid WGS84 bounds")
            except (ValueError, TypeError) as exc:
                counts["invalid_geometry_or_direction"] += 1
                invalid.append({"route_id": route, "source_object": index, "reason": str(exc)})
                continue
            db.execute("INSERT INTO roads VALUES (?)", (route,))  # duplicate IDs fail closed
            x, y = line.centroid.coords[0]
            tile = f"{int(x // 4000)}_{int(y // 4000)}"
            geometry_batch.append({"_tile": tile, "route_id": route,
                "source_attributes_json": json.dumps(attrs, ensure_ascii=False),
                "travel_direction": attrs["TRAVEL_DIRECTION"], "elevation": attrs.get("ELEVATION", ""),
                "length_m": line.length, "geometry_wkb_2326": line.wkb,
                "geometry_wkb_4326": wgs.wkb, "west": west, "south": south,
                "east": east, "north": north})
            counts["parsed_valid_segments"] += 1
            counts["area", tile] += 1
            for arc, rid, a, b in arcs:
                db.execute("INSERT INTO arcs VALUES (?,?,?,?,?,?)", (arc, rid, a, b, tile, line.length))
                arc_batch.append({"_tile": tile, "arc_id": arc, "route_id": rid,
                                  "from_node": a, "to_node": b, "length_m": line.length,
                                  "travel_direction": attrs["TRAVEL_DIRECTION"],
                                  "elevation": attrs.get("ELEVATION", "")})
                counts["directed_arcs"] += 1
            if len(geometry_batch) >= batch_size:
                _write_batch(output / "geometry", geometry_batch, counts, "geometry_part")
                _write_batch(output / "arcs", arc_batch, counts, "arc_part")
                geometry_batch, arc_batch = [], []
        if geometry_batch:
            _write_batch(output / "geometry", geometry_batch, counts, "geometry_part")
            _write_batch(output / "arcs", arc_batch, counts, "arc_part")
        db.commit()
        # Intersection point must coincide with the very same source endpoint;
        # interior intersections and grade-separated crossings remain unconnected.
        for attrs, element in read_features(intersections):
            counts["source_intersections"] += 1
            point = element.find(".//{*}Point")
            if point is None or point.get("srsName") != "EPSG:2326":
                raise ValueError("Unexpected INTERSECTION CRS/geometry")
            x, y = map(float, point.findtext("{*}pos", "").split())
            for rid in {v for k, v in attrs.items() if k.startswith("RD_ID_") and v}:
                # 1m tolerance solely for evidentiary tagging; not for new edges.
                for node, in db.execute("SELECT DISTINCT from_node FROM arcs WHERE route=? UNION SELECT DISTINCT to_node FROM arcs WHERE route=?", (rid, rid)):
                    nx, ny, _ = node.split(":")
                    if math.hypot(int(nx) / 100 - x, int(ny) / 100 - y) <= 1:
                        db.execute("INSERT INTO intersection_routes VALUES (?,?,?)", (rid, node, attrs["INT_ID"]))
        db.commit()
        for attrs, _ in read_features(turns):
            counts["source_turns"] += 1
            if float(attrs.get("NO_TURN") or "0") >= 0:
                continue
            sequence = [attrs[f"EDGE{i}FID"] for i in range(1, 9) if attrs.get(f"EDGE{i}FID")]
            for a, b in zip(sequence, sequence[1:]):
                db.execute("INSERT INTO restrictions VALUES (?,?,?)", (a, b, attrs["TURN_ID"]))
        db.commit()
        nodes, components, largest = _components(db)
        # Disk-backed join: never materialize all source shapes or arc pairs.
        cursor = db.execute("""SELECT a.arc,b.arc,a.route,b.route,a.to_node,a.tile,
            (SELECT group_concat(DISTINCT i.int_id) FROM intersection_routes i
             JOIN intersection_routes j ON i.int_id=j.int_id AND i.node=j.node
             WHERE i.route=a.route AND j.route=b.route AND i.node=a.to_node),
            (SELECT group_concat(DISTINCT r.turn_id) FROM restrictions r
             WHERE r.from_route=a.route AND r.to_route=b.route)
            FROM arcs a JOIN arcs b ON a.to_node=b.from_node""")
        batch: list[dict] = []
        for from_arc, to_arc, from_route, to_route, node, tile, ints, blocks in cursor:
            status = ("turn_restricted" if blocks else "uturn_unverified" if from_route == to_route
                      else "intersection_supported_candidate" if ints else "endpoint_only_unverified")
            counts["transition", status] += 1
            batch.append({"_tile": tile, "from_arc": from_arc, "to_arc": to_arc,
                "from_route": from_route, "to_route": to_route, "node": node,
                "intersection_ids": ints or "", "restricting_turn_ids": blocks or "",
                "status": status, "human_verified": False})
            if len(batch) >= batch_size:
                _write_batch(output / "transitions", batch, counts, "transition_part")
                batch = []
        if batch:
            _write_batch(output / "transitions", batch, counts, "transition_part")
        (output / "invalid_geometry.json").write_text(json.dumps(invalid, indent=2) + "\n", encoding="utf-8")
        # POSIX ru_maxrss is KiB; Windows lacks resource. Use optional field.
        try:
            import resource
            peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except ImportError:
            peak_kib = None
        report = {"source_segments": counts["source_segments"], "parsed_valid_segments": counts["parsed_valid_segments"],
            "invalid_geometry_or_direction": counts["invalid_geometry_or_direction"], "directed_arcs": counts["directed_arcs"],
            "graph_nodes": nodes, "weak_endpoint_components": components,
            "largest_weak_endpoint_component_nodes": largest,
            "source_intersections": counts["source_intersections"], "source_turns": counts["source_turns"],
            "transition_status_counts": {k[1]: v for k, v in counts.items() if isinstance(k, tuple) and k[0] == "transition"},
            "segments_by_4km_hk1980_tile": {k[1]: v for k, v in counts.items() if isinstance(k, tuple) and k[0] == "area"},
            "crs_source": "EPSG:2326", "crs_visualization": "EPSG:4326",
            "geometry_status": "official_geometry_candidate", "topology_status": "unverified_candidate_not_routable",
            "rounding": "endpoint 1cm; identical source elevation; intersection tag <=1m only",
            "peak_rss_kib_posix": peak_kib, "runtime_seconds": round(time.monotonic() - start, 2),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": {name: {"url": NETWORK_STATIC + name, "path": str(path), "sha256": sha256_file(path),
                "http_metadata": json.loads(path.with_name(path.name + ".meta.json").read_text(encoding="utf-8"))
                if path.with_name(path.name + ".meta.json").exists() else None}
                for name, path in (("CENTERLINE.gml", centerline), ("INTERSECTION.gml", intersections), ("TURN.gml", turns))}}
        (output / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--centerline", type=Path, default=Path("data/local/audit-20261019-21/network_centerline.gml"))
    parser.add_argument("--network-http", type=Path, default=Path("data/local/pilot/network_http"))
    parser.add_argument("--output", type=Path, default=Path("data/local/network-full/v1"))
    args = parser.parse_args()
    result = build_network(args.centerline, args.network_http / "INTERSECTION.gml",
                           args.network_http / "TURN.gml", args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "segments_by_4km_hk1980_tile"}, indent=2))


if __name__ == "__main__":
    main()
