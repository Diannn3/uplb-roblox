from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.modeling.assembly import write_obj_assembly
from tools.modeling.baker_hall import REFERENCE_PATH, SPEC_PATH, compile_baker_hall


def test_baker_reference_profile_has_license_and_no_photo_binaries() -> None:
    profile = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    sources = {row["id"]: row for row in profile["sources"]}
    assert sources["source:image:commons-baker-2017"]["license"] == "CC BY-SA 4.0"
    assert sources["source:image:commons-baker-2023"]["license"] == "CC BY-SA 4.0"
    assert profile["policy"]["photoBinaryPolicy"].startswith("No third-party photo binaries")
    assert not list(REFERENCE_PATH.parent.glob("*.jpg"))
    assert not list(REFERENCE_PATH.parent.glob("*.png"))


def test_baker_v02_is_reference_derived_not_final_truth() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["productionStatus"] == "reference-derived-v0.2"
    assert spec["referenceDerivedApproximation"]["status"] == "provisional-replaceable"
    assert spec["accuracyClaims"]["interior"] == "not-modeled"
    assert "survey" in spec["referenceDerivedApproximation"]["method"].lower()


def test_baker_assembly_is_recognizable_but_budgeted() -> None:
    assembly, report = compile_baker_hall()
    summary = assembly.summary()
    assert summary["partCount"] >= 75
    assert summary["triangleEquivalent"] < 90_000
    assert summary["boundsM"]["size"][2] >= 10.0
    assert 53.0 < report["frontFacade"]["lengthM"] < 55.5
    assert 0.28 < report["frontFacade"]["porticoRatio"] < 0.36
    names = {part.name for part in assembly.parts}
    for required in {
        "body-canonical-footprint",
        "portico-balcony-slab",
        "upper-round-column-01",
        "balustrade-top-rail",
        "central-sign-parapet",
        "central-provisional-gable-roof",
    }:
        assert required in names
    assert report["accuracyClaims"]["exactFacadeDimensions"] == "not surveyed"


def test_baker_obj_output_is_deterministic(tmp_path: Path) -> None:
    assembly, _ = compile_baker_hall()
    path_a = tmp_path / "a.obj"
    path_b = tmp_path / "b.obj"
    hash_a = write_obj_assembly(path_a, assembly)
    hash_b = write_obj_assembly(path_b, assembly)
    assert hash_a == hash_b
    assert hashlib.sha256(path_a.read_bytes()).hexdigest() == hashlib.sha256(path_b.read_bytes()).hexdigest()
