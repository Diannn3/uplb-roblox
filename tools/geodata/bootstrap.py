"""Explicit data bootstrap for offline fixtures and opt-in network acquisition."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .io import read_json, sha256, write_feature_collection, write_json
from .osm import ingest_osm_candidates


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "data" / "raw" / "osm_uplb_aoi.json"
DEFAULT_OUTPUT = ROOT / "data"
DEFAULT_BBOX = ROOT / "research" / "campus_bbox.json"


def build_overpass_query(bbox: dict[str, float]) -> str:
    south, west, north, east = bbox["south"], bbox["west"], bbox["north"], bbox["east"]
    selectors = [
        f'nwr["building"]({south},{west},{north},{east});',
        f'nwr["building:part"]({south},{west},{north},{east});',
        f'way["highway"]({south},{west},{north},{east});',
        f'nwr["entrance"]({south},{west},{north},{east});',
        f'nwr["barrier"]({south},{west},{north},{east});',
        f'nwr["waterway"]({south},{west},{north},{east});',
        f'nwr["natural"="water"]({south},{west},{north},{east});',
        f'nwr["landuse"]({south},{west},{north},{east});',
        f'nwr["leisure"]({south},{west},{north},{east});',
        f'nwr["amenity"="parking"]({south},{west},{north},{east});',
    ]
    return "[out:json][timeout:240];(\n" + "\n".join(selectors) + "\n);out body;>;out geom;"


def fetch_osm(raw_path: Path, bbox_path: Path = DEFAULT_BBOX) -> None:
    bbox = read_json(bbox_path)
    query = build_overpass_query(bbox)
    url = "https://overpass-api.de/api/interpreter?" + urllib.parse.urlencode({"data": query})
    request = urllib.request.Request(url, headers={"User-Agent": "uplb-roblox-geodata/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(response.read())


def bootstrap(
    *,
    raw_path: Path = DEFAULT_RAW,
    output_root: Path = DEFAULT_OUTPUT,
    fetch: bool = False,
    fixture_mode: bool = False,
    accessed_at: str = "2026-08-17",
    expected_hash: str | None = None,
) -> dict[str, Any]:
    if not raw_path.exists():
        if not fetch:
            raise FileNotFoundError(f"missing raw input {raw_path}; use --fetch explicitly or pass a tracked fixture")
        fetch_osm(raw_path)
    actual_hash = sha256(raw_path)
    if expected_hash and actual_hash != expected_hash.removeprefix("sha256:"):
        raise ValueError(f"raw input hash mismatch: expected {expected_hash}, actual sha256:{actual_hash}")
    result = ingest_osm_candidates(raw_path, accessed_at=accessed_at)
    candidate_path = output_root / "candidates" / "osm" / "features.geojson"
    source_path = output_root / "candidates" / "osm" / "source-record.json"
    write_feature_collection(
        candidate_path,
        [feature.to_geojson_feature() for feature in result.features],
        lifecycle="candidate",
        provider="osm",
        fixtureMode=fixture_mode,
    )
    write_json(source_path, result.source.to_dict())
    manifest = {
        "version": 1,
        "mode": "fixture" if fixture_mode else "full",
        "rawPath": str(raw_path),
        "candidatePath": str(candidate_path),
        "sourcePath": str(source_path),
        "candidateCount": len(result.features),
        "skippedElements": result.skipped_elements,
        "contentHash": result.source.content_hash,
        "expectedHash": expected_hash,
    }
    write_json(output_root / "candidates" / "bootstrap-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--accessed-at", default="2026-08-17")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    print(json.dumps(bootstrap(raw_path=args.raw, output_root=args.output, fetch=args.fetch, fixture_mode=args.fixture, accessed_at=args.accessed_at, expected_hash=args.expected_sha256), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
