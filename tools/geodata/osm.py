"""Normalize Overpass JSON into provider candidates.

OSM identifiers are deliberately retained as external evidence IDs. They are
never used as the canonical campus identity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon

from .geometry import GeometryState, inspect_geometry
from .io import geometry_from_osm_points, read_json, sha256
from .models import CanonicalFeature, ProviderCandidate, SourceRecord


@dataclass(frozen=True)
class OSMCandidateIngestResult:
    features: tuple[ProviderCandidate, ...]
    source: SourceRecord
    skipped_elements: int


@dataclass(frozen=True)
class OSMIngestResult:
    """Legacy view retained for callers that explicitly request promotion-like output."""

    features: tuple[CanonicalFeature, ...]
    source: SourceRecord
    skipped_elements: int


def _canonical_id(feature_type: str, name: str, osm_type: str, osm_id: int) -> str:
    folded = name.casefold()
    known = (
        ("baker memorial", "building:baker-hall"),
        ("baker hall", "building:baker-hall"),
        ("freedom park", "landmark:freedom-park"),
        ("oblation", "landmark:oblation"),
    )
    for needle, suffix in known:
        if needle in folded:
            return f"uplb:{suffix}"
    return f"uplb:{feature_type}:osm-{osm_type}-{osm_id}"


def _feature_type(tags: dict[str, Any]) -> str | None:
    if "building" in tags or "building:part" in tags:
        return "building"
    if "highway" in tags:
        return "walkway" if tags["highway"] in {"footway", "path", "pedestrian", "steps", "cycleway"} else "road"
    if "entrance" in tags:
        return "entrance"
    if tags.get("barrier") in {"gate", "fence", "wall"}:
        return "barrier"
    if "waterway" in tags:
        return "waterway"
    if tags.get("natural") == "water" or "water" in tags:
        return "water"
    if tags.get("amenity") == "parking" or "landuse" in tags or "leisure" in tags:
        return "landuse"
    if tags.get("name") and any(key in tags for key in ("amenity", "tourism", "man_made")):
        return "poi"
    return None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def _close_ring(points: list[dict[str, float]]) -> list[dict[str, float]]:
    return [*points, points[0]] if points and points[0] != points[-1] else points


def _point_key(point: dict[str, Any]) -> tuple[float, float]:
    return float(point["lon"]), float(point["lat"])


def _stitch_segments(segments: list[list[dict[str, float]]]) -> list[list[dict[str, float]]]:
    """Join Overpass relation member fragments into explicit rings.

    Overpass may return a multipolygon relation with member ways that only
    represent pieces of a ring.  Exact endpoint matching is intentional: a
    fuzzy join would invent topology and should instead enter review.
    """

    remaining = [list(segment) for segment in segments if len(segment) >= 2]
    rings: list[list[dict[str, float]]] = []
    while remaining:
        ring = remaining.pop(0)
        changed = True
        while changed and ring and _point_key(ring[0]) != _point_key(ring[-1]):
            changed = False
            for index, segment in enumerate(remaining):
                if _point_key(segment[0]) == _point_key(ring[-1]):
                    ring.extend(segment[1:])
                elif _point_key(segment[-1]) == _point_key(ring[-1]):
                    ring.extend(reversed(segment[:-1]))
                elif _point_key(segment[-1]) == _point_key(ring[0]):
                    ring = segment[:-1] + ring
                elif _point_key(segment[0]) == _point_key(ring[0]):
                    ring = list(reversed(segment[1:])) + ring
                else:
                    continue
                remaining.pop(index)
                changed = True
                break
        if _point_key(ring[0]) == _point_key(ring[-1]) and len(ring) >= 4:
            rings.append(ring)
    return rings


def _relation_geometry(
    element: dict[str, Any],
    way_geometries: dict[int, list[dict[str, float]]] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    outer_segments: list[list[dict[str, float]]] = []
    inner_segments: list[list[dict[str, float]]] = []
    member_meta: list[dict[str, Any]] = []
    for member in element.get("members", []):
        points = member.get("geometry")
        if not isinstance(points, list) and way_geometries and member.get("type") == "way":
            try:
                points = way_geometries.get(int(member.get("ref", -1)))
            except (TypeError, ValueError):
                points = None
        member_meta.append({"type": member.get("type"), "ref": member.get("ref"), "role": member.get("role", "")})
        if not isinstance(points, list) or len(points) < 3 or any(not isinstance(point, dict) or not {"lat", "lon"}.issubset(point) for point in points):
            continue
        if member.get("role") == "inner":
            inner_segments.append(points)
        else:
            outer_segments.append(points)
    outers = _stitch_segments(outer_segments)
    inners = _stitch_segments(inner_segments)
    if not outers:
        return None, member_meta
    try:
        outer_polygons = [Polygon([_point_key(point) for point in _close_ring(ring)]) for ring in outers]
    except (TypeError, ValueError):
        return None, member_meta
    holes_by_outer: list[list[list[dict[str, float]]]] = [[] for _ in outers]
    for inner in inners:
        try:
            inner_polygon = Polygon([_point_key(point) for point in _close_ring(inner)])
        except (TypeError, ValueError):
            continue
        owner = next((index for index, outer in enumerate(outer_polygons) if outer.contains(inner_polygon.representative_point())), None)
        if owner is not None:
            holes_by_outer[owner].append(inner)
    polygons = []
    for index, outer_ring in enumerate(outers):
        outer = [[float(point["lon"]), float(point["lat"])] for point in _close_ring(outer_ring)]
        holes = [
            [[float(point["lon"]), float(point["lat"])] for point in _close_ring(ring)]
            for ring in holes_by_outer[index]
        ]
        polygons.append([outer, *holes])
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}, member_meta
    return {"type": "MultiPolygon", "coordinates": polygons}, member_meta


def _element_points(element: dict[str, Any]) -> list[dict[str, float]] | None:
    if isinstance(element.get("geometry"), list):
        return element["geometry"]
    if element.get("type") == "node" and {"lat", "lon"}.issubset(element):
        return [{"lat": float(element["lat"]), "lon": float(element["lon"])}]
    return None


def _geometry_for_element(
    element: dict[str, Any],
    feature_type: str,
    way_geometries: dict[int, list[dict[str, float]]] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if element.get("type") == "relation":
        return _relation_geometry(element, way_geometries)
    points = _element_points(element)
    if not points:
        return None, []
    polygon = feature_type in {"building", "landuse", "water"} and len(points) >= 3
    try:
        return geometry_from_osm_points(points, polygon=polygon), []
    except (KeyError, TypeError, ValueError):
        return None, []


def _properties(tags: dict[str, Any], relation_members: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"osmTags": {key: tags[key] for key in sorted(tags)}}
    if relation_members:
        result["relationMembers"] = relation_members
    if "height" in tags:
        result["heightM"] = _number(tags["height"])
    if "building:levels" in tags:
        result["levels"] = _number(tags["building:levels"])
    for key in ("surface", "access", "oneway", "width", "highway", "waterway", "building", "bridge", "tunnel", "layer", "covered", "incline"):
        if key in tags:
            result[key] = tags[key]
    return result


def _confidence(feature_type: str, tags: dict[str, Any]) -> dict[str, str]:
    has_height = "height" in tags or "building:levels" in tags
    return {
        "position": "medium",
        "footprint": "medium" if feature_type in {"building", "landuse", "water"} else "unknown",
        "height": "medium" if has_height else "unknown",
        "facade": "unknown",
    }


def _source(path: Path, accessed_at: str) -> SourceRecord:
    payload = read_json(path)
    points = []
    for element in payload.get("elements", []):
        if isinstance(element.get("geometry"), list):
            for point in element["geometry"]:
                if not isinstance(point, dict) or not {"lat", "lon"}.issubset(point):
                    continue
                try:
                    points.append((float(point["lon"]), float(point["lat"])))
                except (TypeError, ValueError):
                    continue
        elif {"lat", "lon"}.issubset(element):
            try:
                points.append((float(element["lon"]), float(element["lat"])))
            except (TypeError, ValueError):
                pass
    coverage = None
    if points:
        longitudes, latitudes = zip(*points)
        coverage = {
            "crs": "EPSG:4326",
            "bbox": [min(longitudes), min(latitudes), max(longitudes), max(latitudes)],
        }
    return SourceRecord(
        id=f"source:osm:uplb-aoi@{accessed_at}",
        provider="OpenStreetMap contributors",
        source_url="https://overpass-api.de/api/interpreter",
        accessed_at=accessed_at,
        license="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        redistribution="allowed-with-conditions",
        rights_status="open-attribution-required",
        intended_use=("building-footprint", "road", "walkway", "waterway", "water", "entrance", "barrier", "landuse"),
        status="validated",
        content_hash=f"sha256:{sha256(path)}",
        coverage=coverage,
        notes=("Research AOI only; not an official UPLB boundary.",),
    )


class OSMIngestor:
    def __init__(self, accessed_at: str = "2026-08-17") -> None:
        self.accessed_at = accessed_at

    def ingest_candidates(self, path: Path) -> OSMCandidateIngestResult:
        payload = read_json(path)
        features: list[ProviderCandidate] = []
        skipped = 0
        way_geometries = {
            int(element["id"]): element["geometry"]
            for element in payload.get("elements", [])
            if element.get("type") == "way" and isinstance(element.get("geometry"), list)
        }
        for element in payload.get("elements", []):
            tags = element.get("tags") or {}
            feature_type = _feature_type(tags)
            if feature_type is None:
                skipped += 1
                continue
            geometry, relation_members = _geometry_for_element(element, feature_type, way_geometries)
            if geometry is None:
                skipped += 1
                continue
            geometry_inspection = inspect_geometry(geometry)
            if geometry_inspection.state == GeometryState.REJECTED or geometry_inspection.geometry is None:
                skipped += 1
                continue
            geometry = geometry_inspection.geometry
            osm_type = str(element.get("type", "unknown"))
            try:
                osm_id = int(element["id"])
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            external_key = f"{osm_type}/{osm_id}"
            name = str(tags.get("name") or f"OSM {feature_type} {osm_id}")
            features.append(
                ProviderCandidate(
                    id=f"candidate:osm:{external_key}",
                    provider="osm",
                    feature_type=feature_type,
                    name=name,
                    geometry=geometry,
                    aliases=tuple(filter(None, str(tags.get("alt_name", "")).split(";"))),
                    properties={
                        **_properties(tags, relation_members),
                        "geometryState": geometry_inspection.state.value,
                        "geometryReason": geometry_inspection.reason,
                        "originalGeometryHash": geometry_inspection.original_hash,
                        **({"repairedGeometryHash": geometry_inspection.repaired_hash} if geometry_inspection.repaired_hash else {}),
                        **({"relationId": f"relation/{element['id']}"} if element.get("type") == "relation" else {}),
                    },
                    external_ids={"osm": external_key},
                    provenance=(f"source:osm:uplb-aoi@{self.accessed_at}",),
                    confidence=_confidence(feature_type, tags),
                )
            )
        return OSMCandidateIngestResult(tuple(features), _source(path, self.accessed_at), skipped)

    def ingest(self, path: Path) -> OSMIngestResult:
        candidate_result = self.ingest_candidates(path)
        legacy_features: list[CanonicalFeature] = []
        for candidate in candidate_result.features:
            osm_type, raw_id = candidate.external_ids["osm"].split("/", 1)
            legacy_features.append(
                CanonicalFeature(
                    id=_canonical_id(candidate.feature_type, candidate.name, osm_type, int(raw_id)),
                    feature_type=candidate.feature_type,
                    name=candidate.name,
                    geometry=candidate.geometry,
                    aliases=candidate.aliases,
                    properties=candidate.properties,
                    external_ids=candidate.external_ids,
                    provenance=candidate.provenance,
                    confidence=candidate.confidence,
                    verification_status="needs-site-verification",
                )
            )
        return OSMIngestResult(tuple(legacy_features), candidate_result.source, candidate_result.skipped_elements)


def ingest_osm_candidates(path: Path, accessed_at: str = "2026-08-17") -> OSMCandidateIngestResult:
    return OSMIngestor(accessed_at).ingest_candidates(path)


def ingest_osm(path: Path, accessed_at: str = "2026-08-17") -> OSMIngestResult:
    return OSMIngestor(accessed_at).ingest(path)
