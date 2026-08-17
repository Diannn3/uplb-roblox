from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.modeling.reference_building import OUTPUT_ROOT, generate_central_wave_outputs
from tools.modeling.registry import ROOT


def test_central_wave_manifest_is_schema_valid_and_candidate_safe(tmp_path: Path) -> None:
    # Generation uses the project output location because reports store repo-relative paths.
    reports = generate_central_wave_outputs()
    assert len(reports) >= 6
    manifest = json.loads((OUTPUT_ROOT / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "data/canonical/schemas/central-wave-production-manifest.schema.json").read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(manifest))
    assert all(record["identityStatus"] != "canonical" for record in manifest["records"])
    assert all(record["qaStatus"] == "pass" for record in manifest["records"])


def test_reference_layer_does_not_vendor_photo_binaries() -> None:
    reference_root = ROOT / "data/modeling/reference"
    forbidden = []
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.tif", "*.tiff"):
        forbidden.extend(reference_root.rglob(suffix))
    assert forbidden == []
