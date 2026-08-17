from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from .facade import generate_facade_bays
from .mesh import MeshData, extrude_polygon


def compile_standard_building(
    ring_local_m: Iterable[tuple[float, float]],
    *,
    feature_id: str,
    levels: int,
    floor_height_m: float,
    target_bay_width_m: float,
    window_component_id: str = "window:jalousie-a",
) -> dict[str, Any]:
    """Compile deterministic massing + a facade placement plan for standard buildings.

    The function deliberately does not infer doors, stairs, roof form, or exact
    windows. Those remain evidence-driven overrides in the per-building spec.
    """

    if levels < 1:
        raise ValueError("levels must be >= 1")
    height = levels * floor_height_m
    ring = list(ring_local_m)
    mesh: MeshData = extrude_polygon(ring, height)
    bays = generate_facade_bays(
        ring,
        floors=levels,
        floor_height_m=floor_height_m,
        target_bay_width_m=target_bay_width_m,
    )
    return {
        "schemaVersion": "uplb-procedural-building-plan-v0.1",
        "featureId": feature_id,
        "heightM": height,
        "levels": levels,
        "massMesh": {
            "vertices": [list(row) for row in mesh.vertices],
            "faces": [list(row) for row in mesh.faces],
            "triangleEquivalent": mesh.triangle_equivalent,
        },
        "facade": {
            "status": "procedural-layout-unverified",
            "windowComponentId": window_component_id,
            "placements": [asdict(row) for row in bays],
        },
        "explicitlyNotInferred": ["door locations", "stairs", "roof geometry", "facade ornament", "interior"],
    }
