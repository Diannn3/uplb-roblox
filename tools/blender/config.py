from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GreyboxConfig:
    generator_version: str = "greybox-v0.1"
    default_floor_height_m: float = 3.2
    default_building_height_m: float = 6.0
    default_road_width_m: float = 6.0
    default_walkway_width_m: float = 2.5
    terrain_revision: str = "terrain-v0.1-fixture"
    meters_per_stud: float = 0.28
    terrain_sample_spacing_m: float = 20.0
    terrain_margin_m: float = 60.0
