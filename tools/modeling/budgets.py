from __future__ import annotations

from dataclasses import asdict, dataclass


ROBLOX_PER_MESH_TRIANGLE_LIMIT = 20_000


@dataclass(frozen=True)
class AssetBudget:
    """Building-level budget plus hard per-MeshPart import limits.

    The aggregate budgets are art-direction targets for a complete building.
    Roblox's current general mesh specification limits each individual mesh to
    20,000 triangles, so aggregate and per-mesh budgets must stay distinct.
    """

    aggregate_lod0_triangles: int
    aggregate_lod1_triangles: int
    aggregate_lod2_triangles: int
    aggregate_lod3_triangles: int
    per_meshpart_triangles: int
    max_meshparts: int
    max_material_slots: int
    max_texture_px: int
    collision: str
    cast_shadow: bool
    roblox_level_of_detail: str
    render_fidelity: str

    # Backwards-compatible property names used by Wave 01.
    @property
    def lod0_triangles(self) -> int:
        return self.aggregate_lod0_triangles

    @property
    def lod1_triangles(self) -> int:
        return self.aggregate_lod1_triangles

    @property
    def lod2_triangles(self) -> int:
        return self.aggregate_lod2_triangles

    @property
    def lod3_triangles(self) -> int:
        return self.aggregate_lod3_triangles

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value.update(
            {
                "lod0_triangles": self.lod0_triangles,
                "lod1_triangles": self.lod1_triangles,
                "lod2_triangles": self.lod2_triangles,
                "lod3_triangles": self.lod3_triangles,
                "budgetSemantics": "aggregate-building-targets-plus-hard-per-meshpart-limit",
            }
        )
        return value


BUDGETS = {
    "hero-exterior": AssetBudget(
        100_000,
        45_000,
        15_000,
        3_000,
        ROBLOX_PER_MESH_TRIANGLE_LIMIT,
        24,
        12,
        1024,
        "simple-custom",
        True,
        "SLIM",
        "Automatic",
    ),
    "standard-exterior": AssetBudget(
        45_000,
        20_000,
        7_500,
        1_500,
        ROBLOX_PER_MESH_TRIANGLE_LIMIT,
        16,
        8,
        512,
        "simple-custom",
        True,
        "SLIM",
        "Automatic",
    ),
    "context-exterior": AssetBudget(
        15_000,
        6_000,
        2_000,
        500,
        ROBLOX_PER_MESH_TRIANGLE_LIMIT,
        8,
        4,
        512,
        "box-or-hull",
        False,
        "SLIM",
        "Performance",
    ),
    "background": AssetBudget(
        4_000,
        1_500,
        500,
        150,
        ROBLOX_PER_MESH_TRIANGLE_LIMIT,
        4,
        2,
        256,
        "none",
        False,
        "SLIM",
        "Performance",
    ),
    "environment-hero": AssetBudget(
        30_000,
        12_000,
        4_000,
        750,
        ROBLOX_PER_MESH_TRIANGLE_LIMIT,
        12,
        6,
        512,
        "simple",
        True,
        "SLIM",
        "Automatic",
    ),
}


def budget_for(production_tier: str) -> AssetBudget:
    try:
        return BUDGETS[production_tier]
    except KeyError as exc:
        raise ValueError(f"unsupported production tier: {production_tier}") from exc
