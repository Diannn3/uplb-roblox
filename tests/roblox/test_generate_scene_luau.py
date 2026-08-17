from __future__ import annotations

from pathlib import Path

from tools.roblox.generate_scene_luau import generate, prepare_scene


ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "data/generated/worldgen-v0.1/scene-spec.json"


def test_prepare_scene_adds_runtime_bounds_without_dropping_provenance() -> None:
    import json

    scene = json.loads(SCENE.read_text(encoding="utf-8"))
    prepared = prepare_scene(scene)
    assert prepared["runtimeContract"]["terrainWriter"] == "server"
    assert prepared["metadata"]["generatorVersion"]
    assert len(prepared["objects"]) == len(scene["objects"])
    hero = next(item for item in prepared["objects"] if item["role"] == "hero")
    assert hero["provenance"]["verificationStatus"] in {"candidate", "provisional", "human-reviewed"}
    assert hero["runtime"]["placementAuthority"] == "server"
    assert hero["runtime"]["footprintBoundsLocalMeters"]["minEastM"] <= hero["runtime"]["footprintBoundsLocalMeters"]["maxEastM"]


def test_generation_is_byte_deterministic() -> None:
    first = ROOT / "data/generated/roblox-v0.1/.test-first.lua"
    second = ROOT / "data/generated/roblox-v0.1/.test-second.lua"
    try:
        first_report = generate(SCENE, first)
        second_report = generate(SCENE, second)
        assert first.read_bytes() == second.read_bytes()
        assert first_report["generatedLuauSha256"] == second_report["generatedLuauSha256"]
        assert first_report["objectCount"] == 98
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)


def test_checked_in_runtime_module_is_ascii_and_has_contract_header() -> None:
    runtime = ROOT / "src/Server/Generated/WorldScene.lua"
    source = runtime.read_text(encoding="utf-8")
    assert source.startswith("-- GENERATED FILE.")
    assert "Source SHA256: sha256:" in source
    assert all(ord(char) < 128 for char in source)
    assert "[\"runtimeContract\"]" in source


def test_runtime_projection_contains_oriented_proxy_for_footprints() -> None:
    import json

    scene = json.loads(SCENE.read_text(encoding="utf-8"))
    prepared = prepare_scene(scene)
    building = next(item for item in prepared["objects"] if item["role"] == "context-building")
    assert building["proxy"]["widthM"] > 0
    assert building["proxy"]["depthM"] > 0
    assert "yawDegrees" in building["proxy"]
