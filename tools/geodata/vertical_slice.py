"""Freeze the bounded v0.1 world-generation input slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .geometry import distance_m, inspect_geometry, select_intersecting
from .io import read_json, sha256, write_feature_collection, write_json
from .review_priority import DEFAULT_AREA, DEFAULT_CANDIDATES, _candidate_from_geojson
from .transform import CoordinateTransform


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APPROVED = ROOT / "data" / "reviews" / "approved" / "vertical-slice-review-v1.json"
DEFAULT_CANONICAL = ROOT / "data" / "canonical" / "features.geojson"
DEFAULT_SOURCES = ROOT / "data" / "canonical" / "source-records.json"
DEFAULT_OUTPUT = ROOT / "data" / "vertical-slices" / "v0.1"
SLICE_VERSION = "v0.1"
GENERATOR_VERSION = "vertical-slice-v0.1"
ROLE_ORDER = ("hero", "context-building", "road", "walkway", "water", "green-space", "landmark-placeholder")
TARGETS = {"context-building": 35, "road": 25, "walkway": 25, "water": 5, "green-space": 5}


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def _source_feature_map(candidate_path: Path) -> dict[str, Any]:
    payload = read_json(candidate_path)
    return {str(item.get("id")): item for item in payload.get("features", [])}


def _role(candidate: Any) -> str:
    if candidate.feature_type == "building":
        return "context-building"
    if candidate.feature_type == "road":
        return "road"
    if candidate.feature_type == "walkway":
        return "walkway"
    if candidate.feature_type in {"water", "waterway"}:
        return "water"
    if candidate.feature_type in {"landuse", "green-space", "park"}:
        return "green-space"
    if candidate.feature_type == "landmark":
        return "landmark-placeholder"
    return "exclude"


def _proximity(candidate: Any, heroes: list[Any]) -> float:
    distances: list[float] = []
    for hero in heroes:
        if not candidate.geometry or not hero.geometry:
            continue
        try:
            distances.append(distance_m(candidate.geometry, hero.geometry))
        except (TypeError, ValueError):
            continue
    return min(distances) if distances else 1_000_000.0


def _context_sort(candidate: Any, heroes: list[Any]) -> tuple[float, int, str]:
    return (_proximity(candidate, heroes), 0 if candidate.name and not candidate.name.startswith("OSM ") else 1, candidate.id)


def _feature_properties(
    candidate: Any,
    *,
    role: str,
    feature_id: str,
    canonical_id: str | None,
    source_lifecycle: str,
    detail_tier: int,
    review_row: dict[str, Any] | None,
    canonical_revision: str,
    candidate_source_hash: str,
) -> dict[str, Any]:
    inspection = inspect_geometry(candidate.geometry) if candidate.geometry else None
    verification = dict((review_row or {}).get("verification") or {})
    if not verification:
        verification = {
            "identity": "unknown",
            "position": "source-supported" if candidate.geometry else "unknown",
            "footprint": "source-supported" if candidate.feature_type == "building" and candidate.geometry else "unknown",
            "height": "source-supported" if candidate.feature_type == "building" and candidate.confidence.get("height") not in {None, "unknown"} else "unknown",
            "facade": "unknown",
            "interior": "unknown",
        }
    name = str((review_row or {}).get("name") or candidate.name)
    aliases = list(dict.fromkeys([*(review_row or {}).get("aliases", []), *candidate.aliases]))
    return {
        "featureId": feature_id,
        "candidateId": candidate.id,
        "canonicalId": canonical_id,
        "sourceLifecycle": source_lifecycle,
        "worldgenRole": role,
        "detailTier": detail_tier,
        "name": name,
        "aliases": aliases,
        "provider": candidate.provider,
        "featureType": candidate.feature_type,
        "externalIds": dict(sorted(candidate.external_ids.items())),
        "attributes": candidate.properties,
        "provenance": list(candidate.provenance),
        "confidence": dict(sorted(candidate.confidence.items())),
        "verification": dict(sorted(verification.items())),
        "verificationStatus": "human-reviewed" if review_row else "candidate",
        "geometryConfidence": verification.get("footprint", "unknown"),
        "sourceGeometryHash": inspection.original_hash if inspection else None,
        "canonicalRevision": canonical_revision,
        "candidateSourceHash": candidate_source_hash,
        "generatorVersion": GENERATOR_VERSION,
    }


def build_vertical_slice(
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    candidate_path: Path = DEFAULT_CANDIDATES,
    area_path: Path = DEFAULT_AREA,
    approved_path: Path = DEFAULT_APPROVED,
    canonical_path: Path = DEFAULT_CANONICAL,
    sources_path: Path = DEFAULT_SOURCES,
    buffer_m: float = 120.0,
) -> dict[str, Any]:
    candidates_payload = read_json(candidate_path)
    candidate_source_hash = candidates_payload.get("sourceHash")
    if not isinstance(candidate_source_hash, str) or not candidate_source_hash.startswith("sha256:"):
        raise ValueError("candidate source must carry a sha256: sourceHash")
    candidate_map = {str(item.get("id")): _candidate_from_geojson(item) for item in candidates_payload.get("features", [])}
    area_payload = read_json(area_path)
    area_geometry = next(item["geometry"] for item in area_payload.get("features", []) if item.get("properties", {}).get("role") == "core")
    approved = read_json(approved_path)
    approved_rows = {str(row["candidateId"]): row for row in approved.get("rows", [])}
    hero_rows = [row for row in approved.get("rows", []) if row.get("category") == "hero/reference"]
    hero_ids = [str(row["candidateId"]) for row in hero_rows]
    heroes = [candidate_map[candidate_id] for candidate_id in hero_ids if candidate_id in candidate_map]
    if len(heroes) != 5:
        raise ValueError(f"required hero candidates are incomplete: {hero_ids}")
    slice_candidates = select_intersecting(list(candidate_map.values()), area_geometry, buffer_m=buffer_m)
    slice_map = {candidate.id: candidate for candidate in slice_candidates}
    selected: list[tuple[Any, str, dict[str, Any] | None]] = []
    for row in hero_rows:
        candidate = slice_map.get(str(row["candidateId"]))
        if candidate is not None:
            selected.append((candidate, "hero", row))
    selected_ids = {candidate.id for candidate, _, _ in selected}
    for role, quota in TARGETS.items():
        options = [candidate for candidate in slice_candidates if candidate.id not in selected_ids and _role(candidate) == role]
        for candidate in sorted(options, key=lambda item: _context_sort(item, heroes))[:quota]:
            selected.append((candidate, role, None))
            selected_ids.add(candidate.id)
    if len(selected) < 50:
        options = [candidate for candidate in slice_candidates if candidate.id not in selected_ids and _role(candidate) != "exclude"]
        for candidate in sorted(options, key=lambda item: _context_sort(item, heroes))[: 50 - len(selected)]:
            selected.append((candidate, _role(candidate), None))
            selected_ids.add(candidate.id)
    selected.sort(key=lambda item: (ROLE_ORDER.index(item[1]) if item[1] in ROLE_ORDER else len(ROLE_ORDER), item[0].id))
    canonical_payload = read_json(canonical_path)
    canonical_revision = f"sha256:{sha256(canonical_path)}"
    canonical_by_candidate: dict[str, str] = {}
    for feature in canonical_payload.get("features", []):
        for external_id in (feature.get("properties") or {}).get("externalIds", {}).values():
            canonical_by_candidate[f"candidate:osm:{external_id}"] = str(feature.get("id"))
    features: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    for candidate, role, review_row in selected:
        canonical_id = str((review_row or {}).get("registryMatch") or canonical_by_candidate.get(candidate.id) or "") or None
        feature_id = canonical_id or candidate.id
        lifecycle = "canonical" if canonical_id else "candidate"
        detail_tier = 1 if role in {"hero", "context-building", "road", "walkway", "water", "green-space"} else 0
        properties = _feature_properties(candidate, role=role, feature_id=feature_id, canonical_id=canonical_id, source_lifecycle=lifecycle, detail_tier=detail_tier, review_row=review_row, canonical_revision=canonical_revision, candidate_source_hash=candidate_source_hash)
        if candidate.geometry is None:
            validation_errors.append(f"{candidate.id}: missing geometry")
        else:
            inspection = inspect_geometry(candidate.geometry)
            if inspection.state.value in {"needs-review", "rejected"}:
                validation_errors.append(f"{candidate.id}: geometry {inspection.state.value}")
        features.append({"type": "Feature", "id": feature_id, "geometry": candidate.geometry, "properties": properties})
        if canonical_id:
            bindings.append({"canonicalId": canonical_id, "candidateId": candidate.id, "featureId": feature_id, "sourceLifecycle": lifecycle})
    role_counts = {role: sum(1 for _, selected_role, _ in selected if selected_role == role) for role in ROLE_ORDER}
    hero_names = {str(row.get("name")) for row in hero_rows}
    selected_names = {str(feature["properties"].get("name")) for feature in features}
    required_missing = sorted(hero_names - selected_names)
    selection = {
        "sliceVersion": SLICE_VERSION,
        "generatorVersion": GENERATOR_VERSION,
        "reviewVersion": approved.get("reviewVersion"),
        "approvedReviewHash": approved.get("sourcePackageHash"),
        "candidateSourceHash": candidate_source_hash,
        "canonicalRevision": canonical_revision,
        "areaSource": _relative(area_path),
        "bufferMeters": buffer_m,
        "selectedFeatureCount": len(features),
        "contextFeatureCount": sum(1 for feature in features if feature["properties"]["sourceLifecycle"] == "candidate"),
        "roleCounts": role_counts,
        "requiredHeroes": sorted(hero_names),
        "requiredHeroesMissing": required_missing,
        "selectionPolicy": "required approved heroes plus deterministic nearest context by role; context remains candidate lifecycle",
    }
    source_records = read_json(sources_path).get("sources", [])
    source_ids = sorted({source for feature in features for source in feature["properties"]["provenance"]})
    source_manifest = {
        "sliceVersion": SLICE_VERSION,
        "candidateSourceHash": candidate_source_hash,
        "approvedReviewHash": approved.get("sourcePackageHash"),
        "sources": [record for record in source_records if record.get("id") in source_ids],
        "sourceIds": source_ids,
        "rightsNote": "Context features remain candidate lifecycle and are not canonical promotions.",
    }
    validation = {
        "sliceVersion": SLICE_VERSION,
        "status": "pass" if not validation_errors and not required_missing and 50 <= len(features) <= 150 else "fail",
        "errors": validation_errors + ([f"missing required heroes: {required_missing}"] if required_missing else []),
        "selectedFeatureCount": len(features),
        "requiredHeroesMissing": required_missing,
        "duplicateFeatureIds": len({feature["id"] for feature in features}) != len(features),
        "geometryState": "source geometry retained; no survey-grade claim",
        "canonicalFeatureCount": sum(1 for feature in features if feature["properties"]["sourceLifecycle"] == "canonical"),
        "contextFeatureCount": sum(1 for feature in features if feature["properties"]["sourceLifecycle"] == "candidate"),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    area_output = dict(area_payload)
    area_output.setdefault("properties", {})
    area_output["properties"].update({"sliceVersion": SLICE_VERSION, "bufferMeters": buffer_m, "generatorVersion": GENERATOR_VERSION})
    write_json(output_dir / "area.geojson", area_output)
    write_feature_collection(output_dir / "features.geojson", features, sliceVersion=SLICE_VERSION, lifecycle="mixed", sourceHash=candidate_source_hash)
    write_json(output_dir / "selection.json", selection)
    write_json(output_dir / "canonical-bindings.json", {"sliceVersion": SLICE_VERSION, "canonicalRevision": canonical_revision, "bindings": sorted(bindings, key=lambda item: item["canonicalId"])})
    write_json(output_dir / "source-manifest.json", source_manifest)
    write_json(output_dir / "validation-report.json", validation)
    (output_dir / "README.md").write_text(
        "# UPLB vertical slice v0.1\n\n"
        "This bounded, deterministic input contains the approved Oblation/Freedom Park/Baker Hall/DL Umali/Main Library hero set and useful central context. "
        "Context records retain `sourceLifecycle: candidate`; they are not canonical promotions.\n\n"
        "The slice is an OSM-first greybox input. It carries source geometry and provenance but makes no survey-grade, facade, interior, or campus-wide production claim. "
        "Generate it with `python -m tools.geodata.vertical_slice`.\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"selection": selection, "validation": validation, "features": features}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--approved", type=Path, default=DEFAULT_APPROVED)
    args = parser.parse_args()
    result = build_vertical_slice(args.output, candidate_path=args.candidates, area_path=args.area, approved_path=args.approved)
    print(json.dumps(result["selection"], indent=2, sort_keys=True))
    return 0 if result["validation"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
