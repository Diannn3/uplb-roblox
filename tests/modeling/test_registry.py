from tools.modeling.registry import load_registry


def test_registry_is_cross_reference_clean() -> None:
    registry = load_registry()
    assert registry.validate_cross_references() == []
    summary = registry.summary()
    assert summary["buildingCount"] >= 15
    assert summary["sourceCount"] >= 10
    assert summary["componentCount"] >= 20
    assert summary["canonicalBoundCount"] >= 3


def test_only_reviewed_bindings_are_called_canonical() -> None:
    registry = load_registry()
    by_id = {row.id: row for row in registry.buildings}
    assert by_id["production:baker-hall"].canonical_feature_id == "uplb:building:baker-hall"
    assert by_id["production:physical-sciences"].canonical_feature_id is None
    assert by_id["production:physical-sciences"].proposed_feature_id == "uplb:building:physical-sciences"
