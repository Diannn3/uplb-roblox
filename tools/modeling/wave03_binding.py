from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .baker_hall_v04 import OUTPUT_DIR, SNAPSHOT_PATH, SPEC_PATH
from .evidence import validate_schema
from .placement import build_placement_binding
from .registry import ROOT

SCENE_SPEC_PATH = ROOT / "data/generated/worldgen-v0.1/scene-spec.json"
PLACEMENT_SCHEMA = ROOT / "data/canonical/schemas/building-placement-binding.schema.json"
OUTPUT_PATH = ROOT / "data/modeling/placement-bindings/baker-hall.v0.4.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _find(scene: dict[str, Any], feature_id: str) -> dict[str, Any]:
    matches = [
        obj for obj in scene.get("objects", [])
        if feature_id in {obj.get("featureId"), obj.get("candidateId"), obj.get("id")}
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one scene object for {feature_id}, got {len(matches)}")
    return matches[0]


def build() -> dict[str, Any]:
    spec = _read(SPEC_PATH)
    manifest = _read(OUTPUT_DIR / "asset-manifest.json")
    scene = _read(SCENE_SPEC_PATH)
    binding = build_placement_binding(
        feature_snapshot=_read(SNAPSHOT_PATH),
        production_spec=spec,
        asset_manifest=manifest,
        scene_object=_find(scene, spec["proposedFeatureId"]),
    )
    validate_schema(binding, PLACEMENT_SCHEMA, "Baker v0.4 placement binding")
    if binding["softwareTransformValidation"]["status"] != "pass":
        raise ValueError("Baker v0.4 software transform validation failed")
    return binding


def write() -> dict[str, Any]:
    value = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return value
