from __future__ import annotations

import hashlib
from pathlib import Path

from tools.modeling.assembly import write_obj_assembly
from tools.modeling.reference_building import SPEC_DIR, compile_reference_building


def _spec(name: str) -> Path:
    return SPEC_DIR / f"{name}.v0.1.json"


def test_central_wave_specs_compile_without_canonical_promotion() -> None:
    expected = {
        "dl-umali",
        "student-union",
        "physical-sciences",
        "main-library-ulck",
        "cas-annex-2",
        "dean-legaspi-hall",
    }
    actual = {path.name.split(".v0.1.json")[0] for path in SPEC_DIR.glob("*.v0.1.json")}
    assert expected <= actual
    for slug in sorted(expected):
        assembly, report = compile_reference_building(_spec(slug))
        assert assembly.source_feature_id
        assert assembly.identity_status in {"reviewed-candidate", "proposed-candidate"}
        assert report["status"] == "reference-derived-prototype"
        assert report["qa"]["status"] == "pass"
        assert report["accuracyClaims"]["identity"].startswith("production handle only")
        assert report["frontFacadeProxy"]["selectionMethod"].startswith("longest-edge-proxy")


def test_library_construction_candidate_stays_massing_only() -> None:
    assembly, report = compile_reference_building(_spec("main-library-ulck"))
    assert report["facade"]["preset"] == "massing-only"
    assert report["height"]["confidence"] == "low-placeholder"
    assert len(assembly.parts) == 1
    assert report["roof"]["geometryPolicy"] == "deferred-unknown"


def test_physci_keeps_known_gable_as_deferred_not_invented() -> None:
    assembly, report = compile_reference_building(_spec("physical-sciences"))
    assert report["roof"]["sourceShape"] == "gabled"
    assert report["roof"]["geometryPolicy"] == "deferred-known-shape"
    assert not any("roof" in part.name for part in assembly.parts)


def test_student_union_has_glass_frame_proxy() -> None:
    assembly, report = compile_reference_building(_spec("student-union"))
    names = {part.name for part in assembly.parts}
    assert report["facade"]["preset"] == "glass-frame"
    assert any(name.startswith("front-glass-") for name in names)
    assert any(name.startswith("front-support-") for name in names)


def test_reference_building_obj_is_deterministic(tmp_path: Path) -> None:
    assembly, _ = compile_reference_building(_spec("dl-umali"))
    a = tmp_path / "a.obj"
    b = tmp_path / "b.obj"
    ha = write_obj_assembly(a, assembly)
    hb = write_obj_assembly(b, assembly)
    assert ha == hb
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
