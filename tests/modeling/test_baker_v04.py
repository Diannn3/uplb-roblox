from __future__ import annotations

from tools.modeling.baker_hall_v04 import compile_baker_v04, generate_baker_v04
from tools.modeling.budgets import ROBLOX_PER_MESH_TRIANGLE_LIMIT


def test_baker_v04_uses_reviewed_frontage_and_passes_context_gate(tmp_path) -> None:
    assemblies, report = compile_baker_v04()
    assert report["status"] == "pass"
    assert report["productionStage"] == "visual-review"
    assert report["orientation"]["selectionMethod"] == "reviewed-baseline"
    assert report["orientation"]["lengthM"] < 35.0
    assert report["orientation"]["outwardAzimuthDegrees"] > 230.0
    assert report["frontageContext"]["status"] == "pass"
    assert report["frontageContext"]["bearingDeltaDegrees"] <= 15.0
    for qa in report["qa"].values():
        assert qa["status"] == "pass"
        for part in qa["topology"]["parts"]:
            assert part["triangleEquivalent"] <= ROBLOX_PER_MESH_TRIANGLE_LIMIT
            assert part["topology"]["watertight"] is True

    generated = generate_baker_v04(tmp_path)
    assert generated["manifest"]["visualReviewGate"] == "pending-human"
    assert generated["manifest"]["productionStage"] == "visual-review"
