from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AssetBudget:
    lod0_triangles: int
    lod1_triangles: int
    lod2_triangles: int
    lod3_triangles: int
    max_texture_px: int
    collision: str
    cast_shadow: bool
    roblox_level_of_detail: str
    render_fidelity: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


BUDGETS = {
    "hero-exterior": AssetBudget(100_000, 45_000, 15_000, 3_000, 1024, "simple-custom", True, "SLIM", "Automatic"),
    "standard-exterior": AssetBudget(45_000, 20_000, 7_500, 1_500, 512, "simple-custom", True, "SLIM", "Automatic"),
    "context-exterior": AssetBudget(15_000, 6_000, 2_000, 500, 512, "box-or-hull", False, "SLIM", "Performance"),
    "background": AssetBudget(4_000, 1_500, 500, 150, 256, "none", False, "SLIM", "Performance"),
    "environment-hero": AssetBudget(30_000, 12_000, 4_000, 750, 512, "simple", True, "SLIM", "Automatic"),
}


def budget_for(production_tier: str) -> AssetBudget:
    try:
        return BUDGETS[production_tier]
    except KeyError as exc:
        raise ValueError(f"unsupported production tier: {production_tier}") from exc
