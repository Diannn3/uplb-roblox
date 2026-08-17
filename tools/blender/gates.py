"""Explicit execution gates for semantic, real Blender, and Roblox stages."""

from __future__ import annotations

from typing import Any


def build_execution_gates(
    *,
    semantic_status: str,
    terrain_source_kind: str,
    blender_available: bool,
    mesh_status: str,
    render_status: str,
    visual_status: str,
    roblox_status: str,
    roblox_spatial_status: str = "not-run",
    roblox_playtest_status: str = "not-run",
) -> dict[str, Any]:
    return {
        "semanticGate": semantic_status,
        "terrainRealDataGate": "pass" if terrain_source_kind == "real-nasa-raster" else "blocked",
        "blenderAvailableGate": "pass" if blender_available else "blocked",
        "blenderMeshGate": mesh_status,
        "blenderRenderGate": render_status,
        "blenderVisualGate": visual_status,
        "robloxGenerationGate": roblox_status,
        "robloxSpatialGate": roblox_spatial_status,
        "robloxPlaytestGate": roblox_playtest_status,
    }
