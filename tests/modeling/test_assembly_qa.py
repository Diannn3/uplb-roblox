from __future__ import annotations

from tools.modeling.qa import validate_assembly_geometry
from tools.modeling.reference_building import SPEC_DIR, compile_reference_building


def test_reference_geometry_qa_fails_closed_on_bad_budget() -> None:
    assembly, _ = compile_reference_building(SPEC_DIR / "student-union.v0.1.json")
    qa = validate_assembly_geometry(assembly, triangle_budget=1)
    assert qa["status"] == "fail"
    assert qa["triangleBudgetGate"] == "fail"


def test_reference_geometry_qa_has_no_invalid_faces() -> None:
    assembly, _ = compile_reference_building(SPEC_DIR / "cas-annex-2.v0.1.json")
    qa = validate_assembly_geometry(assembly, triangle_budget=100000)
    assert qa["status"] == "pass"
    assert qa["nonFiniteVertexCount"] == 0
    assert qa["invalidFaceIndexCount"] == 0
    assert qa["degenerateFaceCount"] == 0
