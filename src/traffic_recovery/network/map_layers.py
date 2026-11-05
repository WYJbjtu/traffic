"""Viewport-sized exploratory map data; never certify version or graph legality."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds
from pyproj import Transformer
from shapely import wkb


def available_tiles(network: Path) -> list[str]:
    """List official source centroid tiles from construction manifest, not browser state."""
    manifest = json.loads((network / "manifest.json").read_text(encoding="utf-8"))
    return sorted(manifest["segments_by_4km_hk1980_tile"])


def load_tile(network: Path, tile: str, observations: Path | None = None,
              *, max_roads: int = 3000) -> pd.DataFrame:
    """Load only one 4km centroid tile, simplify for browser (EPSG:4326).

    Raw official geometry stays unchanged in Parquet. Speed flags mean an ID
    overlap in an authentic snapshot, NOT a proven historical geometry join.
    Unmatched, source-invalid and absent speeds remain null/neutral.
    """
    if tile not in available_tiles(network):
        raise ValueError("Unknown map tile")
    folder = network / "geometry" / f"tile={tile}"
    table = ds.dataset(folder, format="parquet").to_table(
        columns=["route_id", "geometry_wkb_4326", "west", "south", "east", "north"])
    if len(table) > max_roads:
        raise ValueError("Tile too large; reduce tile size before display")
    frame = table.to_pandas()
    frame["speed_kmh"] = pd.NA
    frame["speed_status"] = "unavailable"
    if observations is not None:
        if not observations.is_file():
            raise FileNotFoundError(observations)
        speeds = pd.read_parquet(observations)
        if not {"segment_id", "speed_kmh", "valid", "id_match", "irn_version", "observed_at"} <= set(speeds):
            raise ValueError("Processed snapshot schema incomplete")
        if speeds.segment_id.duplicated().any():
            raise ValueError("Duplicate segment/time snapshot key")
        speeds = speeds.loc[speeds.valid.eq("Y") & speeds.speed_kmh.notna() & speeds.id_match,
            ["segment_id", "speed_kmh", "irn_version", "observed_at"]]
        frame = frame.drop(columns="speed_kmh").merge(
            speeds.rename(columns={"segment_id": "route_id"}), on="route_id", how="left", validate="one_to_one")
        frame["speed_status"] = frame.speed_kmh.notna().map({True: "ID-only match; network version unverified",
                                                              False: "unavailable"})
    frame["path"] = frame.geometry_wkb_4326.map(lambda blob: [list(xy) for xy in
        wkb.loads(blob).simplify(0.000025, preserve_topology=True).coords])
    frame["color"] = frame.speed_status.eq("unavailable").map({True: [150, 155, 157, 150],
                                                                   False: [220, 137, 58, 210]})
    return frame.drop(columns="geometry_wkb_4326")


def load_candidate_tile(network: Path, tile: str, *, limit: int = 1200) -> pd.DataFrame:
    """Read unverified directed arcs in same tile, with source endpoints in WGS84."""
    if tile not in available_tiles(network):
        raise ValueError("Unknown map tile")
    frame = ds.dataset(network / "arcs" / f"tile={tile}", format="parquet").to_table().to_pandas()
    if len(frame) > limit:
        frame = frame.iloc[:limit].copy()  # explicit display limit, not research sampling
    transformer = Transformer.from_crs(2326, 4326, always_xy=True)
    def endpoint(node: str) -> list[float]:
        x, y, _ = node.split(":")
        return list(transformer.transform(int(x)/100, int(y)/100))
    frame["start"] = frame.from_node.map(endpoint)
    frame["end"] = frame.to_node.map(endpoint)
    return frame
