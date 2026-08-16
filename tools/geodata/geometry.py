"""Spatial correctness utilities backed by Shapely and projected metres."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree
from shapely.validation import explain_validity, make_valid

from .models import CanonicalFeature, ProviderCandidate


class GeometryState(str, Enum):
    VALID = "valid"
    REPAIRED_SAFE = "repaired-safe"
    NEEDS_REVIEW = "needs-review"
    REJECTED = "rejected"


@dataclass(frozen=True)
class GeometryInspection:
    state: GeometryState
    geometry: dict[str, Any] | None
    reason: str
    original_hash: str
    repaired_hash: str | None = None


_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)
_TO_WGS84 = Transformer.from_crs("EPSG:32651", "EPSG:4326", always_xy=True)


def _hash_geometry(geometry: dict[str, Any]) -> str:
    raw = json.dumps(geometry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def parse_geojson_geometry(geometry: dict[str, Any]) -> Any:
    if not isinstance(geometry, dict) or not geometry.get("type"):
        raise ValueError("geometry must be a GeoJSON object")
    return shape(geometry)


def _unclosed_polygon_ring(geometry: dict[str, Any]) -> bool:
    """Return whether any GeoJSON polygon ring is not explicitly closed.

    Shapely will close a ring while parsing it, so this check must happen on
    the provider payload before validity is evaluated.  The caller can then
    record the repair instead of silently treating provider normalization as
    canonical geometry.
    """

    if geometry.get("type") == "Polygon":
        rings = geometry.get("coordinates", [])
    elif geometry.get("type") == "MultiPolygon":
        rings = [ring for polygon in geometry.get("coordinates", []) for ring in polygon]
    else:
        return False
    return any(
        len(ring) >= 3 and ring[0] != ring[-1]
        for ring in rings
        if isinstance(ring, list)
    )


def _has_harmful_adjacent_duplicate(geometry: dict[str, Any]) -> bool:
    if geometry.get("type") not in {"LineString", "MultiLineString"}:
        return False
    lines = [geometry.get("coordinates", [])] if geometry.get("type") == "LineString" else geometry.get("coordinates", [])
    return any(
        first == second
        for line in lines
        for first, second in zip(line, line[1:])
    )


def inspect_geometry(geometry: dict[str, Any], source_hash: str | None = None) -> GeometryInspection:
    original_hash = source_hash or _hash_geometry(geometry)
    if geometry.get("type") in {"LineString", "LinearRing"} and len(geometry.get("coordinates", [])) < 2:
        return GeometryInspection(GeometryState.REJECTED, None, "degenerate-line", original_hash)
    try:
        parsed = parse_geojson_geometry(geometry)
    except Exception as exc:
        return GeometryInspection(GeometryState.REJECTED, None, f"malformed:{exc}", original_hash)
    if parsed.is_empty:
        return GeometryInspection(GeometryState.REJECTED, None, "empty-geometry", original_hash)
    if parsed.geom_type in {"LineString", "LinearRing"} and len(parsed.coords) < 2:
        return GeometryInspection(GeometryState.REJECTED, None, "degenerate-line", original_hash)
    unclosed = _unclosed_polygon_ring(geometry)
    if _has_harmful_adjacent_duplicate(geometry):
        return GeometryInspection(GeometryState.NEEDS_REVIEW, mapping(parsed), "duplicate-consecutive-coordinate", original_hash)
    if parsed.is_valid:
        if parsed.geom_type in {"Polygon", "MultiPolygon"} and parsed.area <= 1e-14:
            return GeometryInspection(GeometryState.REJECTED, None, "near-zero-area", original_hash)
        if unclosed:
            repaired_mapping = mapping(parsed)
            return GeometryInspection(
                GeometryState.REPAIRED_SAFE,
                repaired_mapping,
                "polygon-ring-closed",
                original_hash,
                _hash_geometry(repaired_mapping),
            )
        return GeometryInspection(GeometryState.VALID, mapping(parsed), "valid", original_hash)
    repaired = make_valid(parsed)
    if repaired.is_empty or not repaired.is_valid:
        return GeometryInspection(GeometryState.REJECTED, None, explain_validity(parsed), original_hash)
    if repaired.geom_type in {"Polygon", "MultiPolygon"} and repaired.area <= 1e-14:
        return GeometryInspection(GeometryState.REJECTED, None, "near-zero-area", original_hash)
    repaired_mapping = mapping(repaired)
    reason = explain_validity(parsed)
    state = GeometryState.REPAIRED_SAFE if repaired.geom_type == parsed.geom_type else GeometryState.NEEDS_REVIEW
    if state == GeometryState.NEEDS_REVIEW:
        # Preserve the provider geometry when repair changes its topology (for
        # example Polygon -> GeometryCollection).  It remains a candidate in
        # an explicit review state rather than silently changing semantics.
        return GeometryInspection(state, mapping(parsed), reason, original_hash, _hash_geometry(repaired_mapping))
    return GeometryInspection(state, repaired_mapping, reason, original_hash, _hash_geometry(repaired_mapping))


def _project(geometry: Any) -> Any:
    return shapely_transform(_TO_UTM.transform, geometry)


def _unproject(geometry: Any) -> Any:
    return shapely_transform(_TO_WGS84.transform, geometry)


def geometry_intersects(left: dict[str, Any], right: dict[str, Any], buffer_m: float = 0.0) -> bool:
    left_shape = _project(parse_geojson_geometry(left))
    right_shape = _project(parse_geojson_geometry(right))
    if buffer_m:
        right_shape = right_shape.buffer(buffer_m)
    return left_shape.intersects(right_shape)


def select_intersecting(
    features: Iterable[CanonicalFeature | ProviderCandidate],
    area_geometry: dict[str, Any],
    buffer_m: float = 0.0,
) -> list[CanonicalFeature | ProviderCandidate]:
    area = _project(parse_geojson_geometry(area_geometry))
    if buffer_m:
        area = area.buffer(buffer_m)
    candidates = list(features)
    geometries = []
    geometry_features: list[CanonicalFeature | ProviderCandidate] = []
    for feature in candidates:
        if feature.geometry is None:
            continue
        try:
            geometries.append(_project(parse_geojson_geometry(feature.geometry)))
            geometry_features.append(feature)
        except (TypeError, ValueError):
            continue
    if not geometries:
        return []
    tree = STRtree(geometries)
    retained: list[CanonicalFeature | ProviderCandidate] = []
    retained_ids: set[str] = set()
    for index in tree.query(area):
        index = int(index)
        if geometries[index].intersects(area):
            feature = geometry_features[index]
            if feature.id not in retained_ids:
                retained.append(feature)
                retained_ids.add(feature.id)
    return sorted(retained, key=lambda feature: feature.id)


def representative_point(geometry: dict[str, Any]) -> tuple[float, float]:
    point = parse_geojson_geometry(geometry).representative_point()
    return float(point.x), float(point.y)


def centroid_projected(geometry: dict[str, Any]) -> tuple[float, float]:
    point = _project(parse_geojson_geometry(geometry)).centroid
    return float(point.x), float(point.y)


def area_m2(geometry: dict[str, Any]) -> float:
    return float(_project(parse_geojson_geometry(geometry)).area)


def length_m(geometry: dict[str, Any]) -> float:
    return float(_project(parse_geojson_geometry(geometry)).length)


def distance_m(left: dict[str, Any], right: dict[str, Any]) -> float:
    return float(_project(parse_geojson_geometry(left)).distance(_project(parse_geojson_geometry(right))))


def iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_shape = _project(parse_geojson_geometry(left))
    right_shape = _project(parse_geojson_geometry(right))
    union = left_shape.union(right_shape).area
    return float(left_shape.intersection(right_shape).area / union) if union else 0.0
