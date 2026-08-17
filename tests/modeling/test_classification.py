from tools.modeling.classification import classify_building
from tools.modeling.registry import load_registry


def test_existing_scan_beats_reconstruction_fallback() -> None:
    registry = load_registry()
    building = next(row for row in registry.buildings if row.id == "production:physical-sciences")
    result = classify_building(building, (registry.sources[source_id] for source_id in building.source_ids))
    assert result.strategy == "existing-scan-with-permission"
    assert result.score >= 50


def test_legacy_model_recovery_is_prioritized_for_baker() -> None:
    registry = load_registry()
    building = next(row for row in registry.buildings if row.id == "production:baker-hall")
    result = classify_building(building, (registry.sources[source_id] for source_id in building.source_ids))
    assert result.strategy == "recover-existing"
    assert "legacy UPLB 3D project evidence exists" in result.reasons
