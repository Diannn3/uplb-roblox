from __future__ import annotations

from pathlib import Path

from tools.terrain.sample import HeightField


def load_terrain(path: Path) -> HeightField:
    return HeightField.read(path)


def ground_height(field: HeightField, east_m: float, north_m: float) -> float:
    return field.ground_height(east_m, north_m)
