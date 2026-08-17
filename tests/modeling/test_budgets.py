from tools.modeling.budgets import budget_for


def test_hero_budget_descends_by_lod() -> None:
    budget = budget_for("hero-exterior")
    assert budget.lod0_triangles > budget.lod1_triangles > budget.lod2_triangles > budget.lod3_triangles
    assert budget.roblox_level_of_detail == "SLIM"


def test_context_assets_disable_shadows_by_default() -> None:
    assert budget_for("context-exterior").cast_shadow is False
