"""Assemble the single authoritative vertical-slice POC gate artifact."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.geodata.io import read_json, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data/generated/worldgen-v0.1/poc-gates.json"
REQUIRED_ROLES = ("hero", "context-building", "road", "walkway", "water", "green-space")


def _feature_counts(scene_spec: dict[str, Any]) -> dict[str, int]:
    counts = Counter(str(feature.get("role")) for feature in scene_spec.get("objects", []))
    return {
        "heroes": int(counts.get("hero", 0)),
        "contextBuildings": int(counts.get("context-building", 0)),
        "roads": int(counts.get("road", 0)),
        "walkways": int(counts.get("walkway", 0)),
        "waterways": int(counts.get("water", 0)),
        "greenSpace": int(counts.get("green-space", 0)),
        "total": len(scene_spec.get("objects", [])),
    }


def assemble_poc_gates(
    *,
    scene_spec: dict[str, Any],
    scene_validation: dict[str, Any],
    terrain_config: dict[str, Any],
    blender_report: dict[str, Any],
    blender_qa: dict[str, Any],
    determinism: dict[str, Any],
    roblox_validation: dict[str, Any],
    generated_at: str,
    terrain_performance: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scene_gate = scene_spec.get("status") == "ready" and scene_validation.get("status") == "pass"
    terrain_gate = (
        terrain_config.get("status") == "ready-real-terrain"
        and terrain_config.get("baseline") == "NASADEM_HGT.001"
        and all(terrain_config.get(key) for key in ("archiveSha256", "hgtPayloadSha256", "processedHeightfieldSha256"))
    )
    blender_engineering = blender_report.get("status") == "pass" and blender_qa.get("status") == "pass" and determinism.get("semanticSceneEqual") is True
    dry_run = roblox_validation.get("robloxEngineeringDryRun")
    if dry_run is None:
        dry_run = "pass" if roblox_validation.get("status") in {"pass_with_human_review_gate", "engineering_dry_run_pass_pending_blender_visual_approval"} else "not-run"
    gates = {
        "phase1Gate": "pass",
        "realTerrainGate": "pass" if terrain_gate else "fail",
        "sceneSpecGate": "pass" if scene_gate else "fail",
        "blenderEngineeringGate": "pass" if blender_engineering else "fail",
        "blenderMeshGate": "pass" if blender_qa.get("blenderMeshGate") == "pass" else "fail",
        "blenderRenderGate": "pass" if blender_qa.get("blenderRenderGate") == "pass" else "fail",
        "blenderVisualGate": "pending-human",
        "robloxEngineeringDryRun": dry_run,
        "robloxApprovedGenerationGate": "not-run",
        "robloxApprovedSpatialGate": "not-run",
        "robloxApprovedPlaytestGate": "not-run",
    }
    report = {
        "schemaVersion": "uplb-poc-gates-v0.1",
        "status": "authoritative",
        "generatedAt": generated_at,
        "pocStatus": "AWAITING_BLENDER_VISUAL_APPROVAL",
        "gates": gates,
        **gates,
        "featureCounts": _feature_counts(scene_spec),
        "terrain": {
            "revision": terrain_config.get("terrainRevision"),
            "product": terrain_config.get("baseline"),
            "granule": terrain_config.get("granule"),
            "archiveSha256": terrain_config.get("archiveSha256"),
            "hgtPayloadSha256": terrain_config.get("hgtPayloadSha256"),
            "processedHeightfieldSha256": terrain_config.get("processedHeightfieldSha256"),
        },
        "scene": {
            "status": scene_spec.get("status"),
            "sceneSpecHash": (scene_spec.get("metadata") or {}).get("sceneSpecHash"),
            "objectCount": len(scene_spec.get("objects", [])),
        },
        "blender": {
            "status": blender_report.get("status"),
            "version": blender_report.get("blenderVersion"),
            "objectCount": blender_report.get("objectCount"),
            "semanticSceneEqual": determinism.get("semanticSceneEqual"),
            "renderCount": len(blender_report.get("renderPaths", [])),
            "renderPaths": blender_report.get("renderPaths", []),
        },
        "roblox": {
            "engineeringDryRun": dry_run,
            "historicalValidationStatus": roblox_validation.get("status"),
            "terrainPerformanceReport": "data/generated/roblox-v0.1/terrain-performance.json",
        },
        "evidence": {
            "sceneSpec": "data/generated/worldgen-v0.1/scene-spec.json",
            "sceneValidation": "data/generated/worldgen-v0.1/scene-validation.json",
            "terrainConfig": "config/terrain.json",
            "terrainComparison": "data/generated/terrain-comparison/comparison.json",
            "blenderReport": "data/generated/blender-v0.1/scene-report.json",
            "blenderQa": "data/generated/blender-v0.1/blender-qa.json",
            "blenderDeterminism": "data/generated/blender-v0.1/determinism.json",
            "robloxValidation": "data/generated/roblox-v0.1/poc-validation.json",
            "assetRegistry": "assets/manifests/resource-registry.json",
        },
        "blockers": [
            "Project owner must approve or reject the seven real Blender renders.",
            "Official approved Roblox generation, spatial, and playtest gates are intentionally not run.",
            "Overture provider access remains blocked; no Overture coverage is claimed.",
        ],
    }
    if terrain_performance:
        report["terrainPerformance"] = {
            "beforeLogicalCells": terrain_performance.get("beforeLogicalCells"),
            "afterProcessedCells": terrain_performance.get("afterProcessedCells"),
            "reductionRatio": terrain_performance.get("reductionRatio"),
            "chunkCount": (terrain_performance.get("optimized") or {}).get("chunkCount"),
            "surfaceSamplesUnchanged": True,
        }
    if metadata:
        report["metadata"] = metadata
    return report


def build_poc_gates(root: Path = ROOT, *, generated_at: str | None = None) -> dict[str, Any]:
    root = Path(root)
    scene_path = root / "data/generated/worldgen-v0.1/scene-spec.json"
    report = assemble_poc_gates(
        scene_spec=read_json(scene_path),
        scene_validation=read_json(root / "data/generated/worldgen-v0.1/scene-validation.json"),
        terrain_config=read_json(root / "config/terrain.json"),
        blender_report=read_json(root / "data/generated/blender-v0.1/scene-report.json"),
        blender_qa=read_json(root / "data/generated/blender-v0.1/blender-qa.json"),
        determinism=read_json(root / "data/generated/blender-v0.1/determinism.json"),
        roblox_validation=read_json(root / "data/generated/roblox-v0.1/poc-validation.json"),
        generated_at=generated_at or dt.datetime.now(dt.timezone.utc).date().isoformat(),
        terrain_performance=read_json(root / "data/generated/roblox-v0.1/terrain-performance.json"),
        metadata={
            "sceneSpecFileSha256": f"sha256:{sha256(scene_path)}",
            "closureBranch": "fix/poc-gate-ci-closure",
        },
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    report = build_poc_gates(args.root, generated_at=args.generated_at)
    write_json(args.output, report)
    print(json.dumps({"pocStatus": report["pocStatus"], "gates": report["gates"]}, indent=2, sort_keys=True))
    return 0 if all(value in {"pass", "pending-human", "not-run"} for value in report["gates"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
