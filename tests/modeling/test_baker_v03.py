from __future__ import annotations

from tools.modeling.baker_hall_v03 import compile_baker_v03, generate_baker_v03
from tools.modeling.budgets import ROBLOX_PER_MESH_TRIANGLE_LIMIT


def test_baker_v03_is_deterministic_prototype_with_stable_names(tmp_path) -> None:
    assemblies, report = compile_baker_v03()
    assert report["status"] == "pass"
    assert report["productionStage"] == "prototype"
    assert report["orientation"]["selectionMethod"] == "longest-edge-proxy"
    assert report["orientationGate"]["status"] == "pass"
    counts = [assemblies[key].mesh.triangle_equivalent for key in ("lod0", "lod1", "lod2", "lod3")]
    assert counts == sorted(counts, reverse=True)
    for qa in report["qa"].values():
        assert qa["status"] == "pass"
        for part in qa["topology"]["parts"]:
            assert part["triangleEquivalent"] <= ROBLOX_PER_MESH_TRIANGLE_LIMIT
            assert part["topology"]["watertight"] is True

    generated = generate_baker_v03(tmp_path)
    manifest = generated["manifest"]
    assert manifest["visualReviewGate"] == "pending-human"
    assert manifest["exchange"]["blenderExportStatus"] == "pending-local-blender"
    assert set(manifest["stableMeshNames"]) >= {"Baker__Shell_A", "Baker__Roof", "Baker__Collision"}
