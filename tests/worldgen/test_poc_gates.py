from __future__ import annotations

import json
from pathlib import Path

from tools.worldgen.poc_gates import assemble_poc_gates


ROOT = Path(__file__).resolve().parents[2]


def test_poc_gate_assembly_keeps_blender_visual_and_approved_roblox_gates_open() -> None:
    scene = {
        "status": "ready",
        "metadata": {"sceneSpecHash": "sha256:scene"},
        "terrain": {"revision": "terrain-v0.2-real", "product": "NASADEM_HGT.001"},
        "objects": [
            {"role": "hero"},
            {"role": "context-building"},
            {"role": "road"},
            {"role": "walkway"},
            {"role": "water"},
            {"role": "green-space"},
        ],
    }
    artifact = assemble_poc_gates(
        scene_spec=scene,
        scene_validation={"status": "pass"},
        terrain_config={
            "status": "ready-real-terrain",
            "baseline": "NASADEM_HGT.001",
            "granule": "NASADEM_HGT_n14e121",
            "archiveSha256": "sha256:archive",
            "hgtPayloadSha256": "sha256:hgt",
            "processedHeightfieldSha256": "sha256:processed",
            "terrainRevision": "terrain-v0.2-real",
        },
        blender_report={"status": "pass", "blenderVersion": "5.0.0", "objectCount": 108, "renderPaths": ["a.png"]},
        blender_qa={"status": "pass", "blenderMeshGate": "pass", "blenderRenderGate": "pass", "semanticSceneEqual": True},
        determinism={"semanticSceneEqual": True},
        roblox_validation={"robloxEngineeringDryRun": "pass"},
        generated_at="2026-08-17",
    )

    assert artifact["status"] == "authoritative"
    assert artifact["pocStatus"] == "AWAITING_BLENDER_VISUAL_APPROVAL"
    assert artifact["gates"]["blenderVisualGate"] == "pending-human"
    assert artifact["gates"]["robloxEngineeringDryRun"] == "pass"
    assert artifact["gates"]["robloxApprovedGenerationGate"] == "not-run"
    assert artifact["featureCounts"]["heroes"] == 1
    assert artifact["featureCounts"]["total"] == 6


def test_checked_in_poc_gate_artifact_is_authoritative_and_validated() -> None:
    artifact = json.loads((ROOT / "data/generated/worldgen-v0.1/poc-gates.json").read_text(encoding="utf-8"))

    assert artifact["status"] == "authoritative"
    assert artifact["pocStatus"] == "ROBLOX_VERTICAL_SLICE_VALIDATED"
    assert artifact["gates"]["realTerrainGate"] == "pass"
    assert artifact["gates"]["blenderVisualGate"] == "approved"
    assert artifact["gates"]["robloxEngineeringDryRun"] == "pass"
    assert all(artifact["gates"][name] == "pass" for name in ("robloxApprovedGenerationGate", "robloxApprovedSpatialGate", "robloxApprovedPlaytestGate"))


def test_approved_visual_review_and_roblox_validation_promote_poc_status() -> None:
    render_paths = [f"C:/review/{name}.png" for name in ("topdown", "oblation", "freedom", "baker", "dl-umali", "road", "library")]
    review = {
        "approvalStatus": "approved",
        "reviewer": "project-owner",
        "approvedAt": "2026-08-17T00:00:00+08:00",
        "renders": [{"path": path, "sha256": "sha256:" + "a" * 64} for path in render_paths],
    }
    artifact = assemble_poc_gates(
        scene_spec={"status": "ready", "metadata": {"sceneSpecHash": "sha256:scene"}, "objects": [{"role": role} for role in ("hero", "context-building", "road", "walkway", "water", "green-space")]},
        scene_validation={"status": "pass"},
        terrain_config={"status": "ready-real-terrain", "baseline": "NASADEM_HGT.001", "granule": "g", "archiveSha256": "sha256:a", "hgtPayloadSha256": "sha256:b", "processedHeightfieldSha256": "sha256:c", "terrainRevision": "terrain-v0.2-real"},
        blender_report={"status": "pass", "blenderVersion": "5.0.0", "objectCount": 108, "renderPaths": render_paths},
        blender_qa={"status": "pass", "blenderMeshGate": "pass", "blenderRenderGate": "pass"},
        determinism={"semanticSceneEqual": True},
        roblox_validation={"robloxEngineeringDryRun": "pass", "approvedGates": {"robloxApprovedGenerationGate": "pass", "robloxApprovedSpatialGate": "pass", "robloxApprovedPlaytestGate": "pass"}},
        visual_review=review,
        generated_at="2026-08-17",
    )

    assert artifact["pocStatus"] == "ROBLOX_VERTICAL_SLICE_VALIDATED"
    assert artifact["blenderVisualGate"] == "approved"
    assert artifact["robloxApprovedGenerationGate"] == "pass"
    assert artifact["robloxApprovedSpatialGate"] == "pass"
    assert artifact["robloxApprovedPlaytestGate"] == "pass"
