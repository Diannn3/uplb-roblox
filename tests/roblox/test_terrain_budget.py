from __future__ import annotations

from tools.roblox.terrain_budget import estimate_terrain_budget


def _scene() -> dict:
    return {
        "terrain": {
            "rows": 3,
            "columns": 3,
            "samplingResolutionM": 30,
            "originEastM": 0,
            "originNorthM": 0,
            "relativeMinElevationM": 0,
            "relativeMaxElevationM": 120,
            "values": [[0, 30, 60], [10, 40, 70], [20, 50, 80]],
        },
        "objects": [
            {
                "geometry": {
                    "coordinatesLocalMeters": [[[0, 0], [300, 0], [300, 300], [0, 300], [0, 0]]]
                }
            }
        ],
    }


def test_budget_preserves_every_column_and_reports_large_reduction() -> None:
    report = estimate_terrain_budget(_scene(), chunk_cells=16, resolution_studs=4, base_depth_cells=4, surface_padding_cells=1)

    assert report["beforeLogicalCells"] == report["baseline"]["xCells"] * report["baseline"]["yCells"] * report["baseline"]["zCells"]
    assert report["afterProcessedCells"] == report["optimized"]["processedCells"]
    assert report["reductionRatio"] > 0.5
    assert report["optimized"]["chunkCount"] > 1
    assert report["optimized"]["columnCount"] == report["baseline"]["xCells"] * report["baseline"]["zCells"]
    assert report["optimized"]["boundaryCoverage"] is True
    assert all(chunk["minY"] <= chunk["minGroundY"] <= chunk["maxY"] for chunk in report["optimized"]["chunks"])
    assert all(chunk["minY"] <= chunk["maxGroundY"] <= chunk["maxY"] for chunk in report["optimized"]["chunks"])


def test_budget_chunk_ranges_are_deterministic_and_nonempty() -> None:
    first = estimate_terrain_budget(_scene(), chunk_cells=8)
    second = estimate_terrain_budget(_scene(), chunk_cells=8)

    assert first == second
    assert all(chunk["yCells"] >= 1 for chunk in first["optimized"]["chunks"])
    assert all(chunk["xCells"] <= 8 and chunk["zCells"] <= 8 for chunk in first["optimized"]["chunks"])
