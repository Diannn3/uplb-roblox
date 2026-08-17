from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any, Iterable

from .assembly import BuildingAssembly
from .mesh import MeshData


def _face_edges(face: tuple[int, ...]) -> Iterable[tuple[int, int]]:
    for index, start in enumerate(face):
        end = face[(index + 1) % len(face)]
        yield (start, end) if start < end else (end, start)


def mesh_topology_report(mesh: MeshData) -> dict[str, Any]:
    """Return deterministic manifold/watertight diagnostics without optional deps."""

    edge_counts: Counter[tuple[int, int]] = Counter()
    degenerate_faces = 0
    invalid_face_indices = 0
    vertex_count = len(mesh.vertices)
    used_vertices: set[int] = set()
    adjacency: dict[int, set[int]] = defaultdict(set)

    for face in mesh.faces:
        if len(face) < 3 or len(set(face)) < 3:
            degenerate_faces += 1
            continue
        if any(index < 0 or index >= vertex_count for index in face):
            invalid_face_indices += 1
            continue
        used_vertices.update(face)
        for edge in _face_edges(face):
            edge_counts[edge] += 1
            adjacency[edge[0]].add(edge[1])
            adjacency[edge[1]].add(edge[0])

    boundary_edges = sorted(edge for edge, count in edge_counts.items() if count == 1)
    overconnected_edges = sorted(edge for edge, count in edge_counts.items() if count > 2)
    manifold_edges = sum(count == 2 for count in edge_counts.values())
    isolated_vertices = sorted(set(range(vertex_count)) - used_vertices)

    component_count = 0
    remaining = set(used_vertices)
    while remaining:
        component_count += 1
        start = min(remaining)
        queue = deque([start])
        remaining.remove(start)
        while queue:
            current = queue.popleft()
            for nxt in sorted(adjacency[current]):
                if nxt in remaining:
                    remaining.remove(nxt)
                    queue.append(nxt)

    status = "pass"
    if boundary_edges or overconnected_edges or degenerate_faces or invalid_face_indices or isolated_vertices:
        status = "fail"

    return {
        "status": status,
        "vertexCount": vertex_count,
        "faceCount": len(mesh.faces),
        "triangleEquivalent": mesh.triangle_equivalent,
        "uniqueEdgeCount": len(edge_counts),
        "manifoldEdgeCount": manifold_edges,
        "boundaryEdgeCount": len(boundary_edges),
        "overconnectedEdgeCount": len(overconnected_edges),
        "degenerateFaceCount": degenerate_faces,
        "invalidFaceIndexCount": invalid_face_indices,
        "isolatedVertexCount": len(isolated_vertices),
        "connectedComponentCount": component_count,
        "watertight": not boundary_edges and not overconnected_edges and not invalid_face_indices,
        "boundaryEdgeSample": [list(edge) for edge in boundary_edges[:12]],
        "overconnectedEdgeSample": [list(edge) for edge in overconnected_edges[:12]],
    }


def assembly_topology_report(
    assembly: BuildingAssembly,
    *,
    aggregate_triangle_budget: int | None = None,
    per_meshpart_triangle_budget: int = 20_000,
    max_meshparts: int | None = None,
) -> dict[str, Any]:
    """Validate each named assembly part as a prospective Roblox MeshPart.

    Per-part topology is the important import gate. The merged mesh is reported
    separately because intentionally overlapping modular parts are not expected
    to form a single manifold shell.
    """

    assembly.validate()
    parts: list[dict[str, Any]] = []
    failed_parts: list[str] = []
    for part in assembly.parts:
        topology = mesh_topology_report(part.mesh)
        triangle_status = "pass" if part.mesh.triangle_equivalent <= per_meshpart_triangle_budget else "fail"
        row = {
            "name": part.name,
            "triangleEquivalent": part.mesh.triangle_equivalent,
            "triangleBudget": per_meshpart_triangle_budget,
            "triangleBudgetGate": triangle_status,
            "topology": topology,
        }
        if topology["status"] != "pass" or triangle_status != "pass":
            failed_parts.append(part.name)
        parts.append(row)

    aggregate = assembly.mesh.triangle_equivalent
    aggregate_status = (
        "not-set" if aggregate_triangle_budget is None else ("pass" if aggregate <= aggregate_triangle_budget else "fail")
    )
    meshpart_status = "not-set" if max_meshparts is None else ("pass" if len(parts) <= max_meshparts else "fail")
    status = "pass"
    if failed_parts or aggregate_status == "fail" or meshpart_status == "fail":
        status = "fail"

    return {
        "status": status,
        "featureId": assembly.feature_id,
        "partCount": len(parts),
        "maxMeshParts": max_meshparts,
        "meshPartCountGate": meshpart_status,
        "aggregateTriangleEquivalent": aggregate,
        "aggregateTriangleBudget": aggregate_triangle_budget,
        "aggregateTriangleBudgetGate": aggregate_status,
        "perMeshPartTriangleBudget": per_meshpart_triangle_budget,
        "failedParts": failed_parts,
        "parts": parts,
    }
