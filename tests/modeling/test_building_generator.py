from tools.modeling.building_generator import compile_standard_building


def test_standard_building_compiles_mass_and_facade_plan() -> None:
    plan = compile_standard_building(
        [(0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)],
        feature_id="uplb:building:test",
        levels=2,
        floor_height_m=3.5,
        target_bay_width_m=3.0,
    )
    assert plan["heightM"] == 7.0
    assert plan["massMesh"]["triangleEquivalent"] >= 12
    assert plan["facade"]["placements"]
    assert "door locations" in plan["explicitlyNotInferred"]
