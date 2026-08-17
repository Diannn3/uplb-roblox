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


def test_checked_in_poc_gate_artifact_is_authoritative_and_human_gated() -> None:
    artifact = json.loads((ROOT / "data/generated/worldgen-v0.1/poc-gates.json").read_text(encoding="utf-8"))

    assert artifact["status"] == "authoritative"
    assert artifact["pocStatus"] == "AWAITING_BLENDER_VISUAL_APPROVAL"
    assert artifact["gates"]["realTerrainGate"] == "pass"
    assert artifact["gates"]["blenderVisualGate"] == "pending-human"
    assert artifact["gates"]["robloxEngineeringDryRun"] == "pass"
    assert all(artifact["gates"][name] == "not-run" for name in ("robloxApprovedGenerationGate", "robloxApprovedSpatialGate", "robloxApprovedPlaytestGate"))
