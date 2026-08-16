"""Normalize an Overpass JSON extract into canonical campus candidates."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .io import geometry_from_osm_points, read_json, sha256
from .models import CanonicalFeature, SourceRecord


@dataclass(frozen=True)
class OSMIngestResult:
    features: tuple[CanonicalFeature, ...]
    source: SourceRecord
    skipped_elements: int


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "unnamed"


def _feature_type(tags: dict[str, Any]) -> str | None:
    if "building" in tags:
        return "building"
    if "highway" in tags:
        return "walkway" if tags["highway"] in {"footway", "path", "pedestrian", "steps", "cycleway"} else "road"
    if "waterway" in tags:
        return "waterway"
    if tags.get("name") and any(key in tags for key in ("amenity", "leisure", "tourism", "man_made", "landuse")):
        return "poi"
    return None


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


def _number(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def _properties(tags: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"osmTags": {key: tags[key] for key in sorted(tags)}}
    if "height" in tags:
        result["heightM"] = _number(tags["height"])
    if "building:levels" in tags:
        result["levels"] = _number(tags["building:levels"])
    for key in ("surface", "access", "oneway", "width", "highway", "waterway", "building"):
        if key in tags:
            result[key] = tags[key]
    return result


def _confidence(feature_type: str, tags: dict[str, Any]) -> dict[str, str]:
    has_height = "height" in tags or "building:levels" in tags
    return {
        "position": "medium",
        "footprint": "medium" if feature_type == "building" else "unknown",
        "height": "medium" if has_height else "unknown",
        "facade": "unknown",
    }


class OSMIngestor:
    """Read only the public, replaceable extract and produce stable candidates."""

    def __init__(self, accessed_at: str = "2026-08-17") -> None:
        self.accessed_at = accessed_at

    def ingest(self, path: Path) -> OSMIngestResult:
        payload = read_json(path)
        features: list[CanonicalFeature] = []
        skipped = 0
        for element in payload.get("elements", []):
            tags = element.get("tags") or {}
            feature_type = _feature_type(tags)
            geometry_points = element.get("geometry")
            if feature_type is None or not isinstance(geometry_points, list):
                skipped += 1
                continue
            name = str(tags.get("name") or f"OSM {feature_type} {element.get('id')}")
            geometry = geometry_from_osm_points(
                geometry_points,
                polygon=feature_type == "building",
            )
            if geometry is None:
                skipped += 1
                continue
            osm_type = str(element.get("type", "unknown"))
            osm_id = int(element["id"])
            feature_id = _canonical_id(feature_type, name, osm_type, osm_id)
            external_key = f"{osm_type}/{osm_id}"
            features.append(
                CanonicalFeature(
                    id=feature_id,
                    feature_type=feature_type,
                    name=name,
                    geometry=geometry,
                    aliases=tuple(filter(None, str(tags.get("alt_name", "")).split(";"))),
                    properties=_properties(tags),
                    external_ids={"osm": external_key},
                    provenance=(f"source:osm:uplb-aoi@{self.accessed_at}",),
                    confidence=_confidence(feature_type, tags),
                    verification_status="needs-site-verification",
                )
            )

        # Source IDs are stable for a pinned extract, while the content hash
        # proves which replaceable file was used for this candidate set.
        source = SourceRecord(
            id=f"source:osm:uplb-aoi@{self.accessed_at}",
            provider="OpenStreetMap contributors",
            source_url="https://overpass-api.de/api/interpreter",
            accessed_at=self.accessed_at,
            license="ODbL-1.0",
            attribution="© OpenStreetMap contributors",
            redistribution="allowed-with-conditions",
            rights_status="open-attribution-required",
            intended_use=("building-footprint", "road", "walkway", "waterway", "landmark-reference"),
            content_hash=f"sha256:{sha256(path)}",
            notes=("Research AOI only; not an official UPLB boundary.",),
        )
        return OSMIngestResult(tuple(features), source, skipped)


def ingest_osm(path: Path, accessed_at: str = "2026-08-17") -> OSMIngestResult:
    return OSMIngestor(accessed_at).ingest(path)
