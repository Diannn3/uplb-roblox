from __future__ import annotations

from tools.modeling.assembly import AssemblyPart, BuildingAssembly
from tools.modeling.budgets import ROBLOX_PER_MESH_TRIANGLE_LIMIT, budget_for
from tools.modeling.mesh import MeshData, box_mesh
from tools.modeling.qa import validate_assembly_geometry


def test_hero_budget_separates_aggregate_from_per_meshpart_limit() -> None:
    budget = budget_for("hero-exterior")
    assert budget.aggregate_lod0_triangles > ROBLOX_PER_MESH_TRIANGLE_LIMIT
    assert budget.per_meshpart_triangles == ROBLOX_PER_MESH_TRIANGLE_LIMIT


def test_qa_rejects_single_meshpart_above_import_limit() -> None:
    base = box_mesh(1, 1, 1)
    # Repeating the six closed box faces gives a topologically over-connected
    # part too; it is unquestionably invalid for the import gate and above the
    # per-MeshPart triangle budget.
    repetitions = 2001
    faces = tuple(face for _ in range(repetitions) for face in base.faces)
    mesh = MeshData(base.vertices, faces)
    assembly = BuildingAssembly("uplb:test", "v1", (AssemblyPart("TooBig", mesh, "x", "test"),))
    report = validate_assembly_geometry(
        assembly,
        triangle_budget=100_000,
        per_meshpart_triangle_budget=20_000,
        max_meshparts=2,
    )
    assert report["status"] == "fail"
    assert report["topology"]["parts"][0]["triangleBudgetGate"] == "fail"
