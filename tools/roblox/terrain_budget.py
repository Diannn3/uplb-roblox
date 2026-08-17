"""Offline Roblox Terrain:WriteVoxels budget estimation.

The report models the server generator's bounded surface-band writes without
requiring Roblox Studio.  It uses the same 4-stud voxel resolution and local
metre/Roblox axis contract as ``WorldGenerator.lua``.
"""

from __future__ import annotations

import math
from typing import Any, Iterable


def _points(value: Any) -> Iterable[tuple[float, float]]:
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        yield float(value[0]), float(value[1])
        return
    if isinstance(value, list):
        for child in value:
            yield from _points(child)


def _terrain_bounds(scene: dict[str, Any], margin_m: float) -> tuple[float, float, float, float]:
    terrain = scene.get("terrain") or {}
    rows = int(terrain.get("rows", 0))
    columns = int(terrain.get("columns", 0))
    spacing_m = float(terrain.get("samplingResolutionM", 0.0))
    origin_east = float(terrain.get("originEastM", 0.0))
    origin_north = float(terrain.get("originNorthM", 0.0))
    terrain_max_east = origin_east + max(columns - 1, 0) * spacing_m
    terrain_max_north = origin_north + max(rows - 1, 0) * spacing_m
    geometry_points = []
    for feature in scene.get("objects", []):
        # Match generate_scene_luau._bounds and WorldGenerator.terrainBounds:
        # use the compiled footprint ring, or the deterministic point proxy
        # when a route has no polygon footprint.  Route centerlines must not
        # silently expand the owned terrain region beyond the runtime contract.
        geometry = feature.get("geometry") or {}
        before = len(geometry_points)
        geometry_points.extend(_points(geometry.get("coordinatesLocalMeters")))
        if len(geometry_points) == before:
            placement = feature.get("placement") or {}
            east, north = placement.get("eastM"), placement.get("northM")
            if isinstance(east, (int, float)) and isinstance(north, (int, float)):
                half = 4.0 if feature.get("role") == "hero" else 2.0
                geometry_points.extend(((float(east) - half, float(north) - half), (float(east) + half, float(north) + half)))
    if geometry_points:
        min_east = min(point[0] for point in geometry_points)
        max_east = max(point[0] for point in geometry_points)
        min_north = min(point[1] for point in geometry_points)
        max_north = max(point[1] for point in geometry_points)
    else:
        min_east, max_east = origin_east, terrain_max_east
        min_north, max_north = origin_north, terrain_max_north
    return (
        max(origin_east, min_east - margin_m),
        min(terrain_max_east, max_east + margin_m),
        max(origin_north, min_north - margin_m),
        min(terrain_max_north, max_north + margin_m),
    )


def _sample_relative_ground_studs(terrain: dict[str, Any], east_m: float, north_m: float) -> float:
    rows = int(terrain.get("rows", 0))
    columns = int(terrain.get("columns", 0))
    spacing_m = float(terrain.get("samplingResolutionM", 0.0))
    origin_east = float(terrain.get("originEastM", 0.0))
    origin_north = float(terrain.get("originNorthM", 0.0))
    values = terrain.get("values") or []
    if rows < 2 or columns < 2 or spacing_m <= 0 or len(values) < rows:
        raise ValueError("scene terrain grid is incomplete")
    col = min(max((east_m - origin_east) / spacing_m, 0.0), columns - 1.0)
    row = min(max((north_m - origin_north) / spacing_m, 0.0), rows - 1.0)
    c0, r0 = math.floor(col), math.floor(row)
    c1, r1 = min(c0 + 1, columns - 1), min(r0 + 1, rows - 1)
    tx, ty = col - c0, row - r0
    try:
        v00 = float(values[r0][c0])
        v10 = float(values[r0][c1])
        v01 = float(values[r1][c0])
        v11 = float(values[r1][c1])
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError("scene terrain grid contains an invalid sample") from exc
    top = v00 + (v10 - v00) * tx
    bottom = v01 + (v11 - v01) * tx
    return (top + (bottom - top) * ty) / 0.28


def estimate_terrain_budget(
    scene: dict[str, Any],
    *,
    chunk_cells: int = 64,
    resolution_studs: int = 4,
    base_depth_cells: int = 4,
    surface_padding_cells: int = 1,
    margin_m: float = 60.0,
) -> dict[str, Any]:
    """Return deterministic before/after voxel counts and chunk bounds."""

    if min(chunk_cells, resolution_studs, base_depth_cells, surface_padding_cells) <= 0:
        raise ValueError("terrain budget parameters must be positive")
    terrain = scene.get("terrain") or {}
    min_east, max_east, min_north, max_north = _terrain_bounds(scene, margin_m)
    min_x = math.floor((min_east / 0.28) / resolution_studs) * resolution_studs
    max_x = math.ceil((max_east / 0.28) / resolution_studs) * resolution_studs
    min_z = math.floor((-max_north / 0.28) / resolution_studs) * resolution_studs
    max_z = math.ceil((-min_north / 0.28) / resolution_studs) * resolution_studs
    relative_min_m = float(terrain.get("relativeMinElevationM", 0.0))
    relative_max_m = float(terrain.get("relativeMaxElevationM", relative_min_m + 1.0))
    min_y = math.floor(((relative_min_m - 4.0) / 0.28) / resolution_studs) * resolution_studs
    max_y = math.ceil(((relative_max_m + 2.0) / 0.28) / resolution_studs) * resolution_studs
    x_cells = max(1, math.floor((max_x - min_x) / resolution_studs))
    z_cells = max(1, math.floor((max_z - min_z) / resolution_studs))
    y_cells = max(1, math.floor((max_y - min_y) / resolution_studs))
    chunks: list[dict[str, Any]] = []
    processed_cells = 0
    column_count = 0
    for x_offset in range(0, x_cells, chunk_cells):
        x_count = min(chunk_cells, x_cells - x_offset)
        for z_offset in range(0, z_cells, chunk_cells):
            z_count = min(chunk_cells, z_cells - z_offset)
            ground: list[list[float]] = []
            for x_index in range(x_count):
                east_m = (min_x + (x_offset + x_index + 0.5) * resolution_studs) * 0.28
                row: list[float] = []
                for z_index in range(z_count):
                    north_m = -((min_z + (z_offset + z_index + 0.5) * resolution_studs) * 0.28)
                    row.append(_sample_relative_ground_studs(terrain, east_m, north_m))
                ground.append(row)
            min_ground = min(value for row in ground for value in row)
            max_ground = max(value for row in ground for value in row)
            chunk_min_y = math.floor((min_ground - base_depth_cells * resolution_studs) / resolution_studs) * resolution_studs
            chunk_max_y = math.ceil((max_ground + surface_padding_cells * resolution_studs) / resolution_studs) * resolution_studs
            chunk_y_cells = max(1, math.floor((chunk_max_y - chunk_min_y) / resolution_studs))
            chunk_cells_processed = x_count * z_count * chunk_y_cells
            processed_cells += chunk_cells_processed
            column_count += x_count * z_count
            chunks.append(
                {
                    "xOffset": x_offset,
                    "zOffset": z_offset,
                    "xCells": x_count,
                    "zCells": z_count,
                    "yCells": chunk_y_cells,
                    "minY": chunk_min_y,
                    "maxY": chunk_max_y,
                    "minGroundY": min_ground,
                    "maxGroundY": max_ground,
                    "processedCells": chunk_cells_processed,
                }
            )
    before_cells = x_cells * y_cells * z_cells
    return {
        "schemaVersion": "roblox-terrain-budget-v0.1",
        "resolutionStuds": resolution_studs,
        "chunkCells": chunk_cells,
        "baseDepthCells": base_depth_cells,
        "surfacePaddingCells": surface_padding_cells,
        "bounds": {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "minZ": min_z, "maxZ": max_z},
        "baseline": {"xCells": x_cells, "yCells": y_cells, "zCells": z_cells, "chunkCount": math.ceil(x_cells / chunk_cells) * math.ceil(z_cells / chunk_cells), "logicalCells": before_cells},
        "optimized": {
            "chunkCount": len(chunks),
            "columnCount": column_count,
            "processedCells": processed_cells,
            "chunks": chunks,
            "boundaryCoverage": column_count == x_cells * z_cells and all(chunk["xCells"] > 0 and chunk["zCells"] > 0 for chunk in chunks),
        },
        "beforeLogicalCells": before_cells,
        "afterProcessedCells": processed_cells,
        "reductionRatio": round(1.0 - (processed_cells / before_cells), 9) if before_cells else 0.0,
        "surfaceContract": "each sampled column is written from chunk-local ground minus base depth through ground plus surface padding; visible ground samples are unchanged",
    }
