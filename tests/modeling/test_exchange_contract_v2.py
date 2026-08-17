from __future__ import annotations

import json
from pathlib import Path

from tools.modeling.budgets import ROBLOX_PER_MESH_TRIANGLE_LIMIT
from tools.modeling.registry import ROOT


def test_baker_exchange_contract_preserves_meshparts_and_defers_studio_preset() -> None:
    manifest = json.loads(
        (ROOT / "assets/generated/production/baker-hall-v0.3/asset-manifest.json").read_text(encoding="utf-8")
    )
    draft = manifest["exchange"]["studioImportPresetDraft"]
    assert draft["worldForward"] == "Front"
    assert draft["worldUp"] == "Top"
    assert draft["mergeMeshes"] is False
    assert draft["insertUsingScenePosition"] is False
    assert draft["useImportedPivot"] is True
    assert draft["status"] == "pending-disposable-studio-bakeoff"
    assert manifest["exchange"]["blenderExportStatus"] == "pending-local-blender"

    for lod in manifest["lods"].values():
        for part in lod["meshParts"]:
            assert part["triangleEquivalent"] <= ROBLOX_PER_MESH_TRIANGLE_LIMIT
    for part in manifest["collision"]["meshParts"]:
        assert part["triangleEquivalent"] <= ROBLOX_PER_MESH_TRIANGLE_LIMIT


def test_blender_handoff_uses_current_axis_contract_without_claiming_validation() -> None:
    script = (ROOT / "tools/blender/build_production_asset.py").read_text(encoding="utf-8")
    assert 'export_yup=True' in script
    assert 'axis_forward="Z"' in script
    assert 'axis_up="Y"' in script
    assert 'studioImportBakeoff": "pending-disposable-studio"' in script
