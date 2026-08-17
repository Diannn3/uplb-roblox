from __future__ import annotations

import math
from typing import Any

from .assembly import BuildingAssembly
from .topology import assembly_topology_report


def _face_area(vertices: tuple[tuple[float, float, float], ...], face: tuple[int, ...]) -> float:
    """Return polygon area magnitude using Newell's method."""
    if len(face) < 3:
        return 0.0
    nx = ny = nz = 0.0
    for i, idx in enumerate(face):
        jdx = face[(i + 1) % len(face)]
        x1, y1, z1 = vertices[idx]
        x2, y2, z2 = vertices[jdx]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def validate_assembly_geometry(
    assembly: BuildingAssembly,
    *,
    triangle_budget: int | None = None,
    per_meshpart_triangle_budget: int = 20_000,
    max_meshparts: int | None = None,
    require_part_watertight: bool = True,
) -> dict[str, Any]:
    """Validate numerical geometry plus Roblox-oriented per-part topology.

    ``triangle_budget`` remains the aggregate building budget for Wave 01
    callers.  ``per_meshpart_triangle_budget`` is the hard import-facing gate.
    """

    assembly.validate()
    mesh = assembly.mesh
    vertex_count = len(mesh.vertices)
    invalid_face_indices = 0
    degenerate_faces = 0
    nonfinite_vertices = 0
    for vertex in mesh.vertices:
        if not all(math.isfinite(value) for value in vertex):
            nonfinite_vertices += 1
    for face in mesh.faces:
        if len(face) < 3 or len(set(face)) < 3:
            degenerate_faces += 1
            continue
        if any(index < 0 or index >= vertex_count for index in face):
            invalid_face_indices += 1
            continue
        if _face_area(mesh.vertices, face) <= 1e-10:
            degenerate_faces += 1

    part_names = [part.name for part in assembly.parts]
    triangle_equivalent = mesh.triangle_equivalent
    aggregate_budget_status = (
        "not-set" if triangle_budget is None else ("pass" if triangle_equivalent <= triangle_budget else "fail")
    )
    topology = assembly_topology_report(
        assembly,
        aggregate_triangle_budget=triangle_budget,
        per_meshpart_triangle_budget=per_meshpart_triangle_budget,
        max_meshparts=max_meshparts,
    )

    status = "pass"
    if nonfinite_vertices or invalid_face_indices or degenerate_faces or len(part_names) != len(set(part_names)):
        status = "fail"
    if aggregate_budget_status == "fail":
        status = "fail"
    if topology["status"] != "pass":
        if require_part_watertight:
            status = "fail"
        elif any(row["triangleBudgetGate"] == "fail" for row in topology["parts"]):
            status = "fail"

    return {
        "status": status,
        "featureId": assembly.feature_id,
        "sourceFeatureId": assembly.source_feature_id,
        "identityStatus": assembly.identity_status,
        "partCount": len(assembly.parts),
        "vertexCount": vertex_count,
        "faceCount": len(mesh.faces),
        "triangleEquivalent": triangle_equivalent,
        "nonFiniteVertexCount": nonfinite_vertices,
        "invalidFaceIndexCount": invalid_face_indices,
        "degenerateFaceCount": degenerate_faces,
        "duplicatePartNames": len(part_names) != len(set(part_names)),
        "triangleBudget": triangle_budget,
        "triangleBudgetGate": aggregate_budget_status,
        "perMeshPartTriangleBudget": per_meshpart_triangle_budget,
        "maxMeshParts": max_meshparts,
        "topology": topology,
    }
