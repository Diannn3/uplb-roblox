"""Fail-closed terrain validation."""

from __future__ import annotations

from typing import Any

from .sample import HeightField


def validate_heightfield(field: HeightField) -> dict[str, Any]:
    errors: list[str] = []
    if field.rows < 2 or field.columns < 2:
        errors.append("heightfield must be at least 2x2")
    if field.spacing_m <= 0:
        errors.append("spacing must be positive")
    if field.vertical_exaggeration <= 0:
        errors.append("vertical exaggeration must be positive")
    if any(not isinstance(value, (int, float)) or value != value for row in field.values for value in row):
        errors.append("heightfield contains NaN/non-numeric values")
    return {"status": "pass" if not errors else "fail", "errors": errors, "rows": field.rows, "columns": field.columns, "minElevationM": field.min_elevation_m if not errors else None, "maxElevationM": field.max_elevation_m if not errors else None}
