from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_server_generation_keeps_authority_and_regeneration_guards() -> None:
    source = (ROOT / "src/Server/WorldGenerator.lua").read_text(encoding="utf-8")
    for required in (
        "Terrain:WriteVoxels",
        "TERRAIN_RESOLUTION",
        "Scene.runtimeContract.regenerationRoot",
        "Refusing to replace an unowned",
        "ParentFeatureId",
        "SegmentIndex",
        "VerificationStatus",
        "CoordinateTransform.LocalToStuds",
    ):
        assert required in source


def test_server_entrypoint_calls_generator_and_handles_late_characters() -> None:
    source = (ROOT / "src/Server/MainServer.server.lua").read_text(encoding="utf-8")
    assert "WorldGenerator.Generate()" in source
    assert "Players.PlayerAdded" in source
    assert "GeneratedSpawnLocation" in source
