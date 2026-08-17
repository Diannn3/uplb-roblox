"""Generate the compact offline candidate fixture used by geodata tests.

The fixture intentionally mirrors the approved vertical-slice hero IDs while
using small deterministic geometries. It is not a source snapshot and must
never be used as production campus data.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "candidate-osm.geojson"
SOURCE_HASH = "sha256:" + ("0" * 64)


def _properties(candidate_id: str, feature_type: str, name: str, index: int) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "provider": "osm",
        "featureType": feature_type,
        "name": name,
        "aliases": [],
        "attributes": {"fixture": True, "fixtureIndex": index},
        "externalIds": {"osm": candidate_id.removeprefix("candidate:osm:")},
        # Keep the provenance shape used by the approved review package; the
        # top-level fixtureNotice still makes the synthetic nature explicit.
        "provenance": ["source:osm:uplb-aoi@2026-08-17"],
        "confidence": {"position": "fixture", "footprint": "fixture", "height": "unknown"},
        "verificationStatus": "candidate",
    }


def _feature(candidate_id: str, feature_type: str, name: str, geometry: dict[str, object], index: int) -> dict[str, object]:
    return {
        "type": "Feature",
        "id": candidate_id,
        "geometry": geometry,
        "properties": _properties(candidate_id, feature_type, name, index),
    }


def _polygon(east: float, north: float, width: float = 0.00016, depth: float = 0.00012) -> dict[str, object]:
    coordinates = [
        [east - width / 2, north - depth / 2],
        [east + width / 2, north - depth / 2],
        [east + width / 2, north + depth / 2],
        [east - width / 2, north + depth / 2],
        [east - width / 2, north - depth / 2],
    ]
    return {"type": "Polygon", "coordinates": [coordinates]}


def _line(east: float, north: float, delta: float = 0.0002) -> dict[str, object]:
    return {"type": "LineString", "coordinates": [[east - delta, north - delta / 3], [east + delta, north + delta / 3]]}


def build() -> dict[str, object]:
    features: list[dict[str, object]] = []
    index = 0

    heroes = [
        ("candidate:osm:node/382803333", "landmark", "UPLB Oblation", {"type": "Point", "coordinates": [121.24155, 14.165]}),
        ("candidate:osm:way/33541968", "landmark", "UPLB Freedom Park", {"type": "Point", "coordinates": [121.24173, 14.16128]}),
        ("candidate:osm:way/37449973", "building", "Charles Fuller Baker Memorial Hall", _polygon(121.2427, 14.16175, 0.00034, 0.0002)),
        ("candidate:osm:way/33541381", "building", "Dioscoro L. Umali Hall", _polygon(121.24135, 14.1641, 0.00028, 0.00018)),
        ("candidate:osm:way/1098780830", "building", "University Library and Knowledge Center", _polygon(121.2421, 14.16265, 0.00024, 0.00016)),
    ]
    for candidate_id, feature_type, name, geometry in heroes:
        features.append(_feature(candidate_id, feature_type, name, geometry, index))
        index += 1

    # Keep all generated context inside the research AOI. The regular spacing
    # makes selection, sorting, and output hashes stable across platforms.
    for kind, count, feature_type, prefix in (
        ("building", 35, "building", "Fixture Building"),
        ("road", 25, "road", "Fixture Road"),
        ("walkway", 25, "walkway", "Fixture Walkway"),
        ("water", 5, "waterway", "Fixture Waterway"),
        ("green", 3, "green-space", "Fixture Green Space"),
    ):
        for ordinal in range(count):
            row = ordinal // 8
            column = ordinal % 8
            east = 121.2390 + column * 0.00085 + (0.00012 if row % 2 else 0.0)
            north = 14.1588 + row * 0.00105 + (0.0001 if kind in {"road", "walkway"} else 0.0)
            candidate_id = f"candidate:osm:fixture/{kind}-{ordinal + 1:03d}"
            if feature_type == "building":
                geometry = _polygon(east, north)
            elif feature_type == "green-space":
                geometry = _polygon(east, north, 0.0003, 0.00022)
            else:
                geometry = _line(east, north, 0.00022 if feature_type == "waterway" else 0.00016)
            features.append(_feature(candidate_id, feature_type, f"{prefix} {ordinal + 1:03d}", geometry, index))
            index += 1

    return {
        "type": "FeatureCollection",
        "lifecycle": "candidate-fixture",
        "sourceHash": SOURCE_HASH,
        "fixtureNotice": "Synthetic offline test data; not a campus source snapshot.",
        "features": features,
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8", newline="\n")
