"""Compare two terrain products at identical local-metre points."""

from __future__ import annotations

import math
from typing import Any

from .sample import HeightField


BASELINE_POLICY_VERSION = "terrain-baseline-v0.2"
BASELINE_METRICS = ["nodataCount", "maxAdjacentDeltaM", "p95AdjacentDeltaM", "spikeCount", "coverageEquality"]


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
    ordered_deltas = sorted(adjacent_deltas)
    median_delta = ordered_deltas[len(ordered_deltas) // 2] if ordered_deltas else 0.0
    spike_threshold = max(5.0, median_delta * 4.0)
    p95_index = min(len(ordered_deltas) - 1, max(0, math.ceil(len(ordered_deltas) * 0.95) - 1)) if ordered_deltas else 0
    return {
        "nodataCount": sum(1 for row in field.values for value in row if field.nodata is not None and value == field.nodata),
        "minElevationM": round(min(values), 6) if values else 0.0,
        "maxElevationM": round(max(values), 6) if values else 0.0,
        "maxAdjacentDeltaM": round(max(adjacent_deltas, default=0.0), 6),
        "p95AdjacentDeltaM": round(ordered_deltas[p95_index], 6) if ordered_deltas else 0.0,
        "medianAdjacentDeltaM": round(median_delta, 6),
        "spikeThresholdM": round(spike_threshold, 6),
        "spikeCount": sum(1 for delta in adjacent_deltas if delta > spike_threshold),
    }


def _field_bounds(field: HeightField) -> dict[str, float]:
    return {
        "westM": round(field.origin_east_m, 6),
        "southM": round(field.origin_north_m, 6),
        "eastM": round(field.origin_east_m + (field.columns - 1) * field.spacing_m, 6),
        "northM": round(field.origin_north_m + (field.rows - 1) * field.spacing_m, 6),
    }


def _slope_safe(field: HeightField, east: float, north: float) -> float | None:
    try:
        return _slope(field, east, north)
    except ValueError:
        return None


def _regular_grid(srtm: HeightField, nasadem: HeightField) -> dict[str, Any]:
    """Sample a deterministic interior grid over the common coverage."""

    west = max(srtm.origin_east_m, nasadem.origin_east_m)
    south = max(srtm.origin_north_m, nasadem.origin_north_m)
    east = min(srtm.origin_east_m + (srtm.columns - 1) * srtm.spacing_m, nasadem.origin_east_m + (nasadem.columns - 1) * nasadem.spacing_m)
    north = min(srtm.origin_north_m + (srtm.rows - 1) * srtm.spacing_m, nasadem.origin_north_m + (nasadem.rows - 1) * nasadem.spacing_m)
    spacing = max(float(srtm.spacing_m), float(nasadem.spacing_m))
    if east <= west or north <= south:
        return {"status": "no-overlap", "rows": 0, "columns": 0, "spacingM": spacing, "validCount": 0, "nodataCount": 0, "samples": []}
    interior_west = min(west + spacing, east)
    interior_east = max(east - spacing, interior_west)
    interior_south = min(south + spacing, north)
    interior_north = max(north - spacing, interior_south)
    columns = min(9, max(3, int(round((interior_east - interior_west) / spacing)) + 1))
    rows = min(9, max(3, int(round((interior_north - interior_south) / spacing)) + 1))
    samples: list[dict[str, Any]] = []
    for row in range(rows):
        northing = interior_south if rows == 1 else interior_south + (interior_north - interior_south) * row / (rows - 1)
        for column in range(columns):
            easting = interior_west if columns == 1 else interior_west + (interior_east - interior_west) * column / (columns - 1)
            item: dict[str, Any] = {"localEastM": round(easting, 6), "localNorthM": round(northing, 6)}
            try:
                srtm_elevation = srtm.ground_height(easting, northing)
                nasadem_elevation = nasadem.ground_height(easting, northing)
                item.update(
                    {
                        "srtmElevationM": round(srtm_elevation, 6),
                        "nasademElevationM": round(nasadem_elevation, 6),
                        "differenceM": round(nasadem_elevation - srtm_elevation, 6),
                        "srtmSlope": _slope_safe(srtm, easting, northing),
                        "nasademSlope": _slope_safe(nasadem, easting, northing),
                        "nodata": False,
                    }
                )
            except ValueError as exc:
                item.update({"error": str(exc), "nodata": True})
            samples.append(item)
    valid = [item for item in samples if "differenceM" in item]
    differences = [abs(float(item["differenceM"])) for item in valid]
    slopes = {
        "srtm": [float(item["srtmSlope"]) for item in valid if item.get("srtmSlope") is not None],
        "nasadem": [float(item["nasademSlope"]) for item in valid if item.get("nasademSlope") is not None],
    }
    return {
        "status": "pass" if valid else "nodata",
        "bounds": {"westM": round(west, 6), "southM": round(south, 6), "eastM": round(east, 6), "northM": round(north, 6)},
        "rows": rows,
        "columns": columns,
        "spacingM": spacing,
        "validCount": len(valid),
        "nodataCount": len(samples) - len(valid),
        "differenceSummary": {
            "meanAbsM": round(sum(differences) / len(differences), 6) if differences else None,
            "maxAbsM": round(max(differences), 6) if differences else None,
        },
        "slopeSummary": {
            key: {"mean": round(sum(values) / len(values), 9) if values else None, "max": round(max(values), 9) if values else None}
            for key, values in slopes.items()
        },
        "samples": samples,
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
    regular_grid = _regular_grid(srtm, nasadem)
    differences = [abs(sample["differenceM"]) for sample in samples.values() if "differenceM" in sample]
    differences.extend(abs(float(sample["differenceM"])) for sample in regular_grid.get("samples", []) if "differenceM" in sample)
    real_raster = srtm.source_kind == "real-nasa-raster" and nasadem.source_kind == "real-nasa-raster"
    return {
        "status": "validated-raster" if real_raster else "fixture-only",
        "baselineSelected": False,
        "selectionReason": "Measured comparison recorded; baseline selection is a separate deterministic decision." if real_raster else "No NASA raster was acquired; fixture results are not evidence for selecting a baseline.",
        "products": [srtm.product, nasadem.product],
        "coverage": {"srtm": _field_bounds(srtm), "nasadem": _field_bounds(nasadem), "overlap": regular_grid.get("bounds")},
        "elevationMinMaxM": {
            "srtm": [round(float(srtm_metrics["minElevationM"]), 6), round(float(srtm_metrics["maxElevationM"]), 6)],
            "nasadem": [round(float(nasadem_metrics["minElevationM"]), 6), round(float(nasadem_metrics["maxElevationM"]), 6)],
        },
        "metrics": {"srtm": srtm_metrics, "nasadem": nasadem_metrics},
        "differenceSummary": {"meanAbsM": round(sum(differences) / len(differences), 6) if differences else None, "maxAbsM": round(max(differences), 6) if differences else None},
        "samples": samples,
        "regularGrid": regular_grid,
        "artifactBehavior": "real-raster-compared" if real_raster else "not-assessed-on-synthetic-fixture",
        "continuity": "measured-adjacent-deltas" if real_raster else "fixture-grid-continuous",
    }


def choose_baseline(comparison: dict[str, Any]) -> dict[str, Any]:
    """Choose a real baseline from a deterministic multi-metric evidence tuple."""

    empty_basis = {"coverageEqual": False, "coverageToleranceM": 1e-6, "scores": {}, "missingMetrics": []}
    if comparison.get("status") != "validated-raster":
        return {
            "baseline": None,
            "policyVersion": BASELINE_POLICY_VERSION,
            "metricsConsidered": BASELINE_METRICS,
            "decisionBasis": empty_basis,
            "selectionReason": "Evidence comparison is unavailable; fixture or blocked results cannot select a terrain baseline.",
        }

    coverage = comparison.get("coverage") or {}
    srtm_bounds = coverage.get("srtm") or {}
    nasadem_bounds = coverage.get("nasadem") or {}
    bound_keys = ("westM", "southM", "eastM", "northM")
    coverage_equal = all(
        isinstance(srtm_bounds.get(key), (int, float))
        and isinstance(nasadem_bounds.get(key), (int, float))
        and math.isclose(float(srtm_bounds[key]), float(nasadem_bounds[key]), abs_tol=1e-6)
        for key in bound_keys
    )
    metrics = comparison.get("metrics") or {}
    scores: dict[str, list[float | int]] = {}
    missing: list[str] = []
    for product_key in ("srtm", "nasadem"):
        product_metrics = metrics.get(product_key) or {}
        required = ("nodataCount", "maxAdjacentDeltaM", "p95AdjacentDeltaM", "spikeCount")
        invalid_keys: list[str] = []
        for key in required:
            value = product_metrics.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                invalid_keys.append(key)
        if invalid_keys:
            missing.extend(f"{product_key}.{key}" for key in invalid_keys)
            continue
        scores[product_key] = [
            int(product_metrics["nodataCount"]),
            float(product_metrics["maxAdjacentDeltaM"]),
            float(product_metrics["p95AdjacentDeltaM"]),
            int(product_metrics["spikeCount"]),
        ]
    basis = {"coverageEqual": coverage_equal, "coverageToleranceM": 1e-6, "scores": scores, "missingMetrics": sorted(set(missing))}
    if not coverage_equal:
        return {
            "baseline": None,
            "policyVersion": BASELINE_POLICY_VERSION,
            "metricsConsidered": BASELINE_METRICS,
            "decisionBasis": basis,
            "selectionReason": "Evidence comparison cannot select a baseline because candidate coverage bounds differ or are not pinned.",
        }
    if missing or len(scores) != 2:
        return {
            "baseline": None,
            "policyVersion": BASELINE_POLICY_VERSION,
            "metricsConsidered": BASELINE_METRICS,
            "decisionBasis": basis,
            "selectionReason": "Evidence comparison cannot select a baseline because one or more required continuity metrics are missing.",
        }

    # Lower is better for every measured component. Prefer SRTM only for a
    # complete tie so the tie-break is explicit and reproducible.
    product_order = {"srtm": 0, "nasadem": 1}
    selected_key = min(scores, key=lambda key: (tuple(scores[key]), product_order[key]))
    baseline = "SRTMGL1.003" if selected_key == "srtm" else "NASADEM_HGT.001"
    return {
        "baseline": baseline,
        "policyVersion": BASELINE_POLICY_VERSION,
        "metricsConsidered": BASELINE_METRICS,
        "decisionBasis": basis,
        "selectionReason": "Evidence comparison selected the product with the lexicographically lowest tuple of nodata count, maximum adjacent delta, p95 adjacent delta, and spike count over equal UPLB AOI coverage.",
    }
