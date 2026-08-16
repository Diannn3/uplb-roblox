"""Compare two terrain products at identical local-metre points."""

from __future__ import annotations

from typing import Any

from .sample import HeightField


def _slope(field: HeightField, east: float, north: float) -> float:
    step = field.spacing_m
    left = field.ground_height(east - step, north)
    right = field.ground_height(east + step, north)
    down = field.ground_height(east, north - step)
    up = field.ground_height(east, north + step)
    rise = ((right - left) / (2 * step)) ** 2 + ((up - down) / (2 * step)) ** 2
    return rise ** 0.5


def compare_products(srtm: HeightField, nasadem: HeightField, points: dict[str, tuple[float, float]]) -> dict[str, Any]:
    samples: dict[str, Any] = {}
    for name, (east, north) in sorted(points.items()):
        try:
            srtm_elevation = srtm.ground_height(east, north)
            nasadem_elevation = nasadem.ground_height(east, north)
            samples[name] = {
                "localEastM": east,
                "localNorthM": north,
                "srtmElevationM": round(srtm_elevation, 6),
                "nasademElevationM": round(nasadem_elevation, 6),
                "differenceM": round(nasadem_elevation - srtm_elevation, 6),
                "srtmSlope": round(_slope(srtm, east, north), 9),
                "nasademSlope": round(_slope(nasadem, east, north), 9),
                "nodata": False,
            }
        except ValueError as exc:
            samples[name] = {"error": str(exc), "nodata": True}
    return {
        "status": "fixture-only" if srtm.source_kind == "synthetic-fixture" or nasadem.source_kind == "synthetic-fixture" else "validated-raster",
        "baselineSelected": False,
        "selectionReason": "No NASA raster was acquired; fixture results are not evidence for selecting a baseline.",
        "products": [srtm.product, nasadem.product],
        "elevationMinMaxM": {
            "srtm": [round(srtm.min_elevation_m, 6), round(srtm.max_elevation_m, 6)],
            "nasadem": [round(nasadem.min_elevation_m, 6), round(nasadem.max_elevation_m, 6)],
        },
        "samples": samples,
        "artifactBehavior": "not-assessed-on-synthetic-fixture",
        "continuity": "fixture-grid-continuous",
    }
