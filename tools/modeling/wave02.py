"""Wave 02: evidence contracts, production placement binding, and Baker v0.3.

This module is deliberately a thin orchestrator around deterministic source
artifacts.  It never promotes candidate geodata, never moves canonical geometry
to fit art, and never claims Blender/Studio QA unless those tools actually ran.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .baker_hall_v03 import (
    MANIFEST_SCHEMA,
    OUTPUT_DIR as BAKER_OUTPUT_DIR,
    PROFILE_SCHEMA,
    REFERENCE_PATH,
    SNAPSHOT_PATH,
    SPEC_PATH,
    SPEC_SCHEMA,
    generate_baker_v03,
)
from .evidence import production_orientation_gate, require_reference_profile_v02, validate_schema
from .freshness import compare_tree, regenerate_and_compare
from .placement import build_placement_binding
from .production_scene import bind_production_assets
from .registry import ROOT

SCENE_SPEC_PATH = ROOT / "data" / "generated" / "worldgen-v0.1" / "scene-spec.json"
PLACEMENT_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "building-placement-binding.schema.json"
REGISTRY_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "production-asset-binding-registry.schema.json"
BINDING_DIR = ROOT / "data" / "modeling" / "placement-bindings"
BAKER_BINDING_PATH = BINDING_DIR / "baker-hall.v0.3.json"
BINDING_REGISTRY_PATH = ROOT / "data" / "modeling" / "production-asset-bindings.json"
REPORT_PATH = ROOT / "data" / "modeling" / "modeling-wave02-report.json"
PRODUCTION_SCENE_PATH = ROOT / "data" / "generated" / "worldgen-v0.1" / "scene-spec.production.json"
BLENDER_SCRIPT = ROOT / "tools" / "blender" / "build_production_asset.py"

WAVE_ID = "modeling-wave02-evidence-integration-v0.1"
SOURCE_BRANCH = "feat/modeling-wave01-continuation"
SOURCE_COMMIT = "43cb34ad567ebbdecccee258413351fa00658dda"
SOURCE_TREE = "915c34f1b1773513e184f65dfaedd148649700ba"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash_payload(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _find_scene_object(scene: dict[str, Any], *, feature_id: str, source_feature_id: str) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for obj in scene.get("objects", []):
        identifiers = {obj.get("featureId"), obj.get("candidateId"), obj.get("id")}
        if feature_id in identifiers or source_feature_id in identifiers or f"scene:{source_feature_id}" in identifiers:
            matches.append(obj)
    if len(matches) > 1:
        raise ValueError(f"multiple scene objects match {feature_id} / {source_feature_id}")
    return matches[0] if matches else None


def validate_inputs() -> dict[str, Any]:
    spec = _read(SPEC_PATH)
    profile = _read(REFERENCE_PATH)
    validate_schema(spec, SPEC_SCHEMA, SPEC_PATH.name)
    validate_schema(profile, PROFILE_SCHEMA, REFERENCE_PATH.name)
    evidence = require_reference_profile_v02(profile)
    orientation = production_orientation_gate(spec)
    if orientation["status"] != "pass":
        raise ValueError("Baker orientation stage gate failed: " + "; ".join(orientation["reasons"]))
    if spec["productionStage"] != "prototype":
        raise ValueError("Wave 02 bundle must not silently promote Baker beyond prototype without project-owner review")
    if spec["orientation"]["policy"] != "longest-edge-proxy":
        raise ValueError("Wave 02 expected unresolved Baker orientation; reviewed orientation must arrive in a later explicit review commit")
    return {"spec": spec, "profile": profile, "evidence": evidence, "orientationGate": orientation}


def build_baker_binding(*, require_scene: bool = True) -> tuple[dict[str, Any], dict[str, Any] | None]:
    inputs = validate_inputs()
    spec = inputs["spec"]
    manifest_path = BAKER_OUTPUT_DIR / "asset-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Baker v0.3 asset manifest is missing; run Wave 02 --generate first")
    manifest = _read(manifest_path)
    validate_schema(manifest, MANIFEST_SCHEMA, manifest_path.name)

    scene = _read(SCENE_SPEC_PATH) if SCENE_SPEC_PATH.exists() else None
    scene_object = None
    if scene is not None:
        scene_object = _find_scene_object(
            scene,
            feature_id=spec["proposedFeatureId"],
            source_feature_id=spec["sourceFeatureId"],
        )
    if require_scene and scene_object is None:
        raise ValueError("authoritative scene spec exists requirement failed: Baker scene object was not found")

    binding = build_placement_binding(
        feature_snapshot=_read(SNAPSHOT_PATH),
        production_spec=spec,
        asset_manifest=manifest,
        scene_object=scene_object,
    )
    validate_schema(binding, PLACEMENT_SCHEMA, "Baker placement binding")
    if require_scene and binding["softwareTransformValidation"]["status"] != "pass":
        raise ValueError("Baker model-local → scene-local software transform validation did not pass")
    return binding, scene


def binding_registry(binding: dict[str, Any]) -> dict[str, Any]:
    manifest_path = BAKER_OUTPUT_DIR / "asset-manifest.json"
    value = {
        "schemaVersion": "uplb-production-asset-binding-registry-v0.1",
        "waveId": WAVE_ID,
        "sourceGit": {"branch": SOURCE_BRANCH, "commit": SOURCE_COMMIT, "treeSha": SOURCE_TREE},
        "records": [
            {
                "featureId": binding["featureId"],
                "sourceFeatureId": binding["sourceFeatureId"],
                "assetId": binding["assetId"],
                "productionStage": _read(manifest_path)["productionStage"],
                "assetManifestPath": "assets/generated/production/baker-hall-v0.3/asset-manifest.json",
                "assetManifestSha256": _sha256(manifest_path),
                "placementBindingPath": "data/modeling/placement-bindings/baker-hall.v0.3.json",
                "placementBindingHash": binding["bindingHash"],
                "scenePlacementAuthority": "canonical-scene",
                "visualReviewGate": _read(manifest_path).get("visualReviewGate", "pending-human"),
            }
        ],
    }
    value["registryHash"] = _hash_payload(value)
    validate_schema(value, REGISTRY_SCHEMA, "production asset binding registry")
    return value


def generate_outputs(*, require_scene: bool = True, write_production_scene: bool = False) -> dict[str, Any]:
    baker = generate_baker_v03(BAKER_OUTPUT_DIR)
    binding, scene = build_baker_binding(require_scene=require_scene)
    _write_json(BAKER_BINDING_PATH, binding)
    registry = binding_registry(binding)
    _write_json(BINDING_REGISTRY_PATH, registry)

    production_scene = None
    if write_production_scene:
        if scene is None:
            raise ValueError("cannot write production scene without authoritative scene spec")
        production_scene = bind_production_assets(scene, [binding])
        _write_json(PRODUCTION_SCENE_PATH, production_scene)

    return {
        "baker": baker,
        "binding": binding,
        "bindingRegistry": registry,
        "productionSceneWritten": bool(production_scene),
    }


def check_freshness(*, require_scene: bool = True) -> dict[str, Any]:
    if not BAKER_OUTPUT_DIR.exists():
        return {"status": "fail", "errors": ["committed Baker v0.3 output directory is missing"]}

    baker_freshness = regenerate_and_compare(BAKER_OUTPUT_DIR, lambda root: generate_baker_v03(root))
    errors: list[str] = []
    if baker_freshness["status"] != "pass":
        errors.append("Baker v0.3 committed artifacts are stale")

    binding_freshness: dict[str, Any] = {"status": "not-checked"}
    registry_freshness: dict[str, Any] = {"status": "not-checked"}
    if BAKER_BINDING_PATH.exists() and BINDING_REGISTRY_PATH.exists():
        expected_binding, _ = build_baker_binding(require_scene=require_scene)
        actual_binding = _read(BAKER_BINDING_PATH)
        binding_freshness = {
            "status": "pass" if actual_binding == expected_binding else "fail",
            "expectedBindingHash": expected_binding["bindingHash"],
            "actualBindingHash": actual_binding.get("bindingHash"),
        }
        if binding_freshness["status"] != "pass":
            errors.append("Baker placement binding is stale")
        expected_registry = binding_registry(expected_binding)
        actual_registry = _read(BINDING_REGISTRY_PATH)
        registry_freshness = {
            "status": "pass" if actual_registry == expected_registry else "fail",
            "expectedRegistryHash": expected_registry["registryHash"],
            "actualRegistryHash": actual_registry.get("registryHash"),
        }
        if registry_freshness["status"] != "pass":
            errors.append("production asset binding registry is stale")
    elif require_scene:
        errors.append("placement binding and production asset binding registry must be committed")

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "bakerArtifacts": baker_freshness,
        "placementBinding": binding_freshness,
        "bindingRegistry": registry_freshness,
    }


def blender_preflight() -> dict[str, Any]:
    executable = shutil.which("blender")
    return {
        "status": "available" if executable else "pending-local-blender",
        "executable": executable,
        "script": str(BLENDER_SCRIPT.relative_to(ROOT)).replace("\\", "/"),
        "claim": "No Blender QA/render/export pass is claimed unless build_production_asset.py completes successfully.",
    }


def run_blender() -> dict[str, Any]:
    executable = shutil.which("blender")
    if not executable:
        raise RuntimeError("Blender is not available on PATH")
    manifest = BAKER_OUTPUT_DIR / "asset-manifest.json"
    command = [
        executable,
        "--background",
        "--python-exit-code",
        "10",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--asset-manifest",
        str(manifest),
        "--output",
        str(BAKER_OUTPUT_DIR / "blender"),
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "returnCode": completed.returncode,
        "command": command,
        "stdoutTail": completed.stdout[-4000:],
        "stderrTail": completed.stderr[-4000:],
    }


def build_report(*, freshness: dict[str, Any] | None = None, generated: bool = False) -> dict[str, Any]:
    inputs = validate_inputs()
    manifest_path = BAKER_OUTPUT_DIR / "asset-manifest.json"
    report = {
        "schemaVersion": "uplb-modeling-wave02-report-v0.1",
        "waveId": WAVE_ID,
        "status": "pass",
        "sourceGit": {"branch": SOURCE_BRANCH, "commit": SOURCE_COMMIT, "treeSha": SOURCE_TREE},
        "implemented": [
            "typed evidence/reference contracts v0.2",
            "review-gated facade orientation policies",
            "Polygon holes and MultiPolygon production extrusion",
            "per-MeshPart topology and 20k-triangle Roblox import gate",
            "formal model-local to canonical-scene placement binding",
            "production asset binding registry",
            "Baker Hall v0.3 stable MeshPart/LOD/collision artifact contract",
            "clean-regeneration freshness checks",
            "Blender production asset/export handoff script",
        ],
        "baker": {
            "productionStage": inputs["spec"]["productionStage"],
            "orientationPolicy": inputs["spec"]["orientation"]["policy"],
            "orientationReviewStatus": inputs["spec"]["orientation"]["reviewStatus"],
            "visualReviewGate": _read(manifest_path).get("visualReviewGate") if manifest_path.exists() else "not-generated",
            "assetManifestSha256": _sha256(manifest_path) if manifest_path.exists() else None,
        },
        "evidenceIntegrity": inputs["evidence"],
        "orientationGate": inputs["orientationGate"],
        "freshness": freshness,
        "blender": blender_preflight(),
        "generatedThisRun": generated,
        "hardStops": [
            "Baker front facade orientation remains a proxy and is not human-reviewed.",
            "No visual-review or production-ready promotion may occur until reviewed orientation evidence is recorded.",
            "No Blender export/QA claim is made on hosts without Blender.",
            "No Roblox Studio import/reimport/playtest claim is made by this offline wave.",
            "Canonical scene placement remains authoritative; art assets may not move geodata.",
        ],
        "nextGate": "Project-owner visual review of real Blender Baker v0.3 renders after orientation is explicitly reviewed, followed by disposable Studio GLB-vs-FBX import/reimport bakeoff.",
    }
    if freshness and freshness["status"] != "pass":
        report["status"] = "fail"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate Wave 02 evidence/spec contracts and hard stops.")
    parser.add_argument("--generate", action="store_true", help="Regenerate Baker v0.3, placement binding, and compact binding registry.")
    parser.add_argument("--check-freshness", action="store_true", help="Regenerate into temp storage and fail on stale committed artifacts.")
    parser.add_argument("--write-report", action="store_true", help="Write data/modeling/modeling-wave02-report.json.")
    parser.add_argument("--write-production-scene", action="store_true", help="Write a large derived scene-spec.production.json for diagnostic consumers. Not needed for source control.")
    parser.add_argument("--allow-missing-scene", action="store_true", help="Testing only: allow a horizontal-only placement binding without the authoritative scene object.")
    parser.add_argument("--run-blender", action="store_true", help="Run the local Blender production handoff if Blender is available.")
    args = parser.parse_args()

    validate_inputs()
    generated = False
    if args.generate:
        generate_outputs(require_scene=not args.allow_missing_scene, write_production_scene=args.write_production_scene)
        generated = True

    freshness = check_freshness(require_scene=not args.allow_missing_scene) if args.check_freshness else None
    blender_result = run_blender() if args.run_blender else None
    report = build_report(freshness=freshness, generated=generated)
    if blender_result is not None:
        report["blenderRun"] = blender_result
        if blender_result["status"] != "pass":
            report["status"] = "fail"
    if args.write_report:
        _write_json(REPORT_PATH, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
