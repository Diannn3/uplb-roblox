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
        "TerrainWriteVoxelsSeconds",
        "TerrainVoxelReductionRatio",
        "TERRAIN_BASE_DEPTH_CELLS",
        "chunkMinGround",
        "SpawnAbsoluteElevationM",
        "ProxyYawDegrees",
    ):
        assert required in source
    assert "ReplicatedStorage.Shared.Generated" not in source


def test_server_entrypoint_uses_explicit_mode_and_positions_each_character_once() -> None:
    source = (ROOT / "src/Server/MainServer.server.lua").read_text(encoding="utf-8")
    assert "WorldgenMode.ShouldGenerate()" in source
    assert "WorldGenerator.Generate()" in source
    assert "Players.PlayerAdded" in source
    assert "GeneratedSpawnLocation" in source
    assert "UPLBSpawnPlaced" in source
    assert "for _ = 1" not in source


def test_heavy_world_scene_is_server_only() -> None:
    assert (ROOT / "src/Server/Generated/WorldScene.lua").exists()
    assert not (ROOT / "src/Shared/Generated/WorldScene.lua").exists()


def test_spawn_anchor_is_offset_from_oblation_proxy_and_samples_its_own_ground() -> None:
    source = (ROOT / "src/Server/WorldGenerator.lua").read_text(encoding="utf-8")
    assert "local proxy = oblation.proxy or {}" in source
    assert "local spawnMarginM = 8" in source
    assert "local spawnEastM = eastM + proxyWidthM / 2 + spawnMarginM" in source
    assert "local spawnRelativeElevationM = sampleTerrain(spawnEastM, spawnNorthM)" in source
    assert 'spawn:SetAttribute("SpawnOffsetEastM", spawnEastM - eastM)' in source
