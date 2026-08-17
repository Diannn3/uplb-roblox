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


def _field_metrics(field: HeightField) -> dict[str, float | int]:
    values = [value for row in field.values for value in row if field.nodata is None or value != field.nodata]
    adjacent_deltas: list[float] = []
    for row in range(field.rows):
        for column in range(field.columns):
            value = field.values[row][column]
            if field.nodata is not None and value == field.nodata:
                continue
            if column + 1 < field.columns:
                neighbor = field.values[row][column + 1]
                if field.nodata is None or neighbor != field.nodata:
                    adjacent_deltas.append(abs(value - neighbor))
            if row + 1 < field.rows:
                neighbor = field.values[row + 1][column]
                if field.nodata is None or neighbor != field.nodata:
                    adjacent_deltas.append(abs(value - neighbor))
    return {
        "nodataCount": sum(1 for row in field.values for value in row if field.nodata is not None and value == field.nodata),
        "minElevationM": round(min(values), 6) if values else 0.0,
        "maxElevationM": round(max(values), 6) if values else 0.0,
        "maxAdjacentDeltaM": round(max(adjacent_deltas, default=0.0), 6),
    }


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
    srtm_metrics = _field_metrics(srtm)
    nasadem_metrics = _field_metrics(nasadem)
    differences = [abs(sample["differenceM"]) for sample in samples.values() if "differenceM" in sample]
    return {
        "status": "fixture-only" if srtm.source_kind == "synthetic-fixture" or nasadem.source_kind == "synthetic-fixture" else "validated-raster",
        "baselineSelected": False,
        "selectionReason": "No NASA raster was acquired; fixture results are not evidence for selecting a baseline.",
        "products": [srtm.product, nasadem.product],
        "elevationMinMaxM": {
            "srtm": [round(float(srtm_metrics["minElevationM"]), 6), round(float(srtm_metrics["maxElevationM"]), 6)],
            "nasadem": [round(float(nasadem_metrics["minElevationM"]), 6), round(float(nasadem_metrics["maxElevationM"]), 6)],
        },
        "metrics": {"srtm": srtm_metrics, "nasadem": nasadem_metrics},
        "differenceSummary": {"meanAbsM": round(sum(differences) / len(differences), 6) if differences else None, "maxAbsM": round(max(differences), 6) if differences else None},
        "samples": samples,
        "artifactBehavior": "not-assessed-on-synthetic-fixture",
        "continuity": "fixture-grid-continuous",
    }


def choose_baseline(comparison: dict[str, Any]) -> dict[str, Any]:
    """Choose a real baseline from measured comparison metrics only."""

    if comparison.get("status") != "validated-raster":
        return {"baseline": None, "selectionReason": "Evidence comparison is unavailable; fixture or blocked results cannot select a terrain baseline."}
    metrics = comparison.get("metrics") or {}
    srtm = metrics.get("srtm") or {}
    nasadem = metrics.get("nasadem") or {}
    if int(srtm.get("nodataCount", 0)) != int(nasadem.get("nodataCount", 0)):
        baseline = "SRTMGL1.003" if int(srtm.get("nodataCount", 0)) < int(nasadem.get("nodataCount", 0)) else "NASADEM_HGT.001"
        return {"baseline": baseline, "selectionReason": "Evidence comparison selected the product with fewer nodata samples in the UPLB AOI."}
    max_difference = comparison.get("differenceSummary", {}).get("maxAbsM")
    if max_difference is not None and float(max_difference) <= 0.5:
        return {"baseline": "SRTMGL1.003", "selectionReason": "Evidence comparison found the products practically indistinguishable in the UPLB AOI; SRTM is retained as the documented baseline without treating product age as evidence."}
    baseline = "SRTMGL1.003" if float(srtm.get("maxAdjacentDeltaM", 0.0)) <= float(nasadem.get("maxAdjacentDeltaM", 0.0)) else "NASADEM_HGT.001"
    return {"baseline": baseline, "selectionReason": "Evidence comparison selected the product with the lower maximum adjacent elevation discontinuity in the UPLB AOI."}
