"""Build the deterministic 25-row vertical-slice human-review package."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from .geometry import (
    area_m2,
    distance_m,
    inspect_geometry,
    length_m,
    parse_geojson_geometry,
    select_intersecting,
)
from .identity import IdentityRegistry, normalize_name
from .io import read_json, write_json
from .models import ProviderCandidate


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = ROOT / "data" / "candidates" / "osm" / "features.geojson"
DEFAULT_AREA = ROOT / "data" / "areas" / "vertical-slice-v0.geojson"
DEFAULT_REGISTRY = ROOT / "data" / "canonical" / "identity-registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "reviews" / "vertical-slice-review.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reviews" / "VERTICAL_SLICE_FEATURE_REVIEW.md"
DEFAULT_GENERATED_AT = "2026-08-17"

QUOTAS = {
    "hero/reference": 5,
    "ordinary building": 8,
    "road/intersection": 5,
    "walkway/pedestrian": 5,
    "environmental": 2,
}

HERO_SPECS = (
    ("UPLB Oblation", ("oblation",)),
    ("UPLB Freedom Park", ("freedom park",)),
    ("Charles Fuller Baker Memorial Hall", ("baker hall", "baker memorial")),
    ("DL Umali Auditorium", ("dioscoro l umali", "umali hall", "umali auditorium")),
    ("Main Library", ("university library", "knowledge center", "main library")),
)


def _candidate_from_geojson(item: dict[str, Any]) -> ProviderCandidate:
    properties = item.get("properties") or {}
    return ProviderCandidate(
        id=str(item.get("id") or properties.get("id")),
        provider=str(properties.get("provider") or "osm"),
        feature_type=str(properties.get("featureType") or "unknown"),
        name=str(properties.get("name") or item.get("id") or "Unnamed candidate"),
        geometry=item.get("geometry"),
        aliases=tuple(str(value) for value in properties.get("aliases", [])),
        properties=dict(properties.get("attributes") or {}),
        external_ids={str(key): str(value) for key, value in (properties.get("externalIds") or {}).items()},
        provenance=tuple(str(value) for value in properties.get("provenance", [])),
        confidence={str(key): str(value) for key, value in (properties.get("confidence") or {}).items()},
        verification_status=str(properties.get("verificationStatus") or "candidate"),
    )


def _area_geometry(area_path: Path) -> dict[str, Any]:
    payload = read_json(area_path)
    feature = next(feature for feature in payload.get("features", []) if feature.get("properties", {}).get("role") == "core")
    return feature["geometry"]


def _hero_match(candidate: ProviderCandidate, aliases: tuple[str, ...]) -> int:
    haystack = normalize_name(" ".join((candidate.name, *candidate.aliases)))
    if any(alias == haystack for alias in aliases):
        return 100
    if any(alias in haystack for alias in aliases):
        return 75
    return 0


def _find_heroes(candidates: list[ProviderCandidate]) -> tuple[list[tuple[str, ProviderCandidate]], list[str]]:
    selected: list[tuple[str, ProviderCandidate]] = []
    used: set[str] = set()
    missing: list[str] = []
    for display_name, aliases in HERO_SPECS:
        options = [
            (candidate, _hero_match(candidate, aliases))
            for candidate in candidates
            if candidate.id not in used and _hero_match(candidate, aliases) > 0
        ]
        if not options:
            missing.append(display_name)
            continue
        candidate, _ = sorted(options, key=lambda item: (-item[1], item[0].id))[0]
        selected.append((display_name, candidate))
        used.add(candidate.id)
    return selected, missing


def _registry_match(candidate: ProviderCandidate, registry: IdentityRegistry) -> str | None:
    return registry.resolve_or_allocate(candidate.feature_type, candidate.name, candidate.external_ids, promote=False)


def _named(candidate: ProviderCandidate) -> bool:
    return bool(candidate.name and not re.match(r"^(OSM|Unnamed)\b", candidate.name, re.IGNORECASE))


def _evidence_richness(candidate: ProviderCandidate) -> int:
    return len(candidate.provenance) * 4 + len(candidate.external_ids) * 3 + len(candidate.properties) + len(candidate.confidence)


def _distance_to_heroes(candidate: ProviderCandidate, hero_candidates: Iterable[ProviderCandidate]) -> float:
    distances = []
    for hero in hero_candidates:
        if candidate.geometry is None or hero.geometry is None:
            continue
        try:
            distances.append(distance_m(candidate.geometry, hero.geometry))
        except (TypeError, ValueError):
            continue
    return min(distances) if distances else 1_000_000.0


def _connectivity_scores(candidates: list[ProviderCandidate]) -> dict[str, int]:
    line_candidates = [candidate for candidate in candidates if candidate.feature_type in {"road", "walkway"} and candidate.geometry]
    shapes = []
    for candidate in line_candidates:
        try:
            shapes.append((candidate, parse_geojson_geometry(candidate.geometry)))
        except (TypeError, ValueError):
            continue
    scores = {candidate.id: 0 for candidate in line_candidates}
    # The threshold is deliberately modest and is only a review-priority hint;
    # it is never used to merge or promote features.
    for index, (candidate, geometry) in enumerate(shapes):
        for other, other_geometry in shapes[index + 1 :]:
            try:
                if geometry.distance(other_geometry) <= 0.00025:
                    scores[candidate.id] += 1
                    scores[other.id] += 1
            except (TypeError, ValueError):
                continue
    return scores


def _direct_connectivity(candidate: ProviderCandidate, hero_candidates: list[ProviderCandidate], connectivity: dict[str, int]) -> int:
    """Return a deterministic direct-hero connectivity signal.

    A line that reaches the hero cluster wins before name/evidence signals. The
    distance threshold is a review-priority heuristic only; it never conflates
    or promotes a candidate.
    """

    if candidate.feature_type not in {"road", "walkway"} or not candidate.geometry:
        return 0
    if connectivity.get(candidate.id, 0) > 0:
        return 1
    for hero in hero_candidates:
        if hero.geometry:
            try:
                if distance_m(candidate.geometry, hero.geometry) <= 35.0:
                    return 1
            except (TypeError, ValueError):
                continue
    return 0


def priority_score(
    candidate: ProviderCandidate,
    category: str,
    registry_id: str | None,
    hero_candidates: list[ProviderCandidate],
    connectivity: dict[str, int],
    core_ids: set[str] | None = None,
) -> tuple[float, ...]:
    """Return a future-review score ordered by spatial usefulness first."""

    named = 1 if _named(candidate) else 0
    registry = 1 if registry_id else 0
    evidence = _evidence_richness(candidate)
    connectivity_score = connectivity.get(candidate.id, 0)
    proximity = _distance_to_heroes(candidate, hero_candidates)
    proximity_score = 1.0 / (1.0 + (proximity / 50.0))
    direct = _direct_connectivity(candidate, hero_candidates, connectivity)
    core = 1 if core_ids and candidate.id in core_ids else 0
    if category == "environmental":
        molawin = 1 if "molawin" in normalize_name(candidate.name) else 0
        return (float(direct), float(core), proximity_score, float(connectivity_score), float(registry), float(molawin), float(named), float(evidence), -proximity)
    return (float(direct), float(core), proximity_score, float(connectivity_score), float(registry), float(named), float(evidence), -proximity)


def _score(
    candidate: ProviderCandidate,
    category: str,
    registry_id: str | None,
    hero_candidates: list[ProviderCandidate],
    connectivity: dict[str, int],
    core_ids: set[str] | None = None,
) -> tuple[float, ...]:
    """Backward-compatible internal alias for the public priority score."""

    return priority_score(candidate, category, registry_id, hero_candidates, connectivity, core_ids)


_HUMAN_FIELDS = (
    "currentDecision",
    "reviewStatus",
    "reviewHistory",
    "review",
    "reviewNotes",
    "sourceName",
    "sourceAliases",
    "correctedName",
    "correctedAliases",
    "canonicalIdentityCorrection",
    "registryMatch",
    "verification",
    "selectedGeometrySource",
    "reviewer",
    "reviewerProvenance",
)


def _overlay_human_state(row: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay human-authored corrections while refreshing provider fields."""

    if not existing:
        return row
    for key in _HUMAN_FIELDS:
        if key in existing:
            row[key] = copy.deepcopy(existing[key])
    # Older review edits stored the corrected value in name/aliases and kept
    # the original in sourceName/sourceAliases. Preserve those edits while
    # allowing all other provider-derived values to refresh.
    if existing.get("correctedName") is not None:
        row["name"] = existing["correctedName"]
    elif existing.get("sourceName") is not None and existing.get("name") != existing.get("sourceName"):
        row["name"] = existing["name"]
    if existing.get("correctedAliases") is not None:
        row["aliases"] = copy.deepcopy(existing["correctedAliases"])
    elif existing.get("sourceAliases") is not None and existing.get("aliases") != existing.get("sourceAliases"):
        row["aliases"] = copy.deepcopy(existing["aliases"])
    return row


def _row(
    candidate: ProviderCandidate,
    category: str,
    registry_id: str | None,
    hero_display_name: str | None,
    priority_score: tuple[float, ...],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inspection = inspect_geometry(candidate.geometry) if candidate.geometry else None
    approximate_position: dict[str, float] | None = None
    magnitude: dict[str, Any] = {"kind": "none", "value": 0.0, "unit": "m"}
    if candidate.geometry:
        try:
            representative = parse_geojson_geometry(candidate.geometry).representative_point()
            approximate_position = {"lon": round(float(representative.x), 7), "lat": round(float(representative.y), 7)}
            if candidate.feature_type == "building" or candidate.geometry.get("type") in {"Polygon", "MultiPolygon"}:
                magnitude = {"kind": "area", "unit": "m2", "value": round(area_m2(candidate.geometry), 3)}
            elif candidate.geometry.get("type") not in {"Point", "MultiPoint"}:
                magnitude = {"kind": "length", "unit": "m", "value": round(length_m(candidate.geometry), 3)}
        except (TypeError, ValueError):
            pass
    aliases = list(dict.fromkeys([*candidate.aliases, *([hero_display_name] if hero_display_name else [])]))
    row = {
        "candidateId": candidate.id,
        "category": category,
        "featureType": candidate.feature_type,
        "name": candidate.name,
        "aliases": aliases,
        "externalIds": dict(sorted(candidate.external_ids.items())),
        "registryMatch": registry_id,
        "geometryStatus": inspection.state.value if inspection else "missing",
        "geometryReason": inspection.reason if inspection else "missing-geometry",
        "sourceGeometryHash": inspection.original_hash if inspection else None,
        "sourceGeometry": candidate.geometry,
        "approximatePosition": approximate_position,
        "areaOrLength": magnitude,
        "provenance": list(candidate.provenance),
        "confidence": dict(sorted(candidate.confidence.items())),
        "evidenceAttributes": candidate.properties,
        "priorityScore": [round(value, 9) for value in priority_score],
        "recommendedAction": (
            "confirm required hero identity, geometry, aliases, and source rights before promotion"
            if hero_display_name
            else "confirm candidate identity, geometry, aliases, and source rights before promotion"
        ),
        "currentDecision": "pending",
        "reviewStatus": "pending",
        "reviewHistory": [],
    }
    return _overlay_human_state(row, existing)


def build_priority_package(
    candidate_path: Path = DEFAULT_CANDIDATES,
    area_path: Path = DEFAULT_AREA,
    registry_path: Path = DEFAULT_REGISTRY,
    output_path: Path = DEFAULT_OUTPUT,
    markdown_path: Path = DEFAULT_MARKDOWN,
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    payload = read_json(candidate_path)
    candidates = [_candidate_from_geojson(item) for item in payload.get("features", [])]
    slice_candidates = select_intersecting(candidates, _area_geometry(area_path), buffer_m=120)
    registry = IdentityRegistry.load(registry_path)
    heroes, missing_heroes = _find_heroes(slice_candidates)
    hero_ids = {candidate.id for _, candidate in heroes}
    hero_candidates = [candidate for _, candidate in heroes]
    connectivity = _connectivity_scores(slice_candidates)
    core_candidates = select_intersecting(candidates, _area_geometry(area_path), buffer_m=0)
    core_ids = {candidate.id for candidate in core_candidates}
    by_category: dict[str, list[ProviderCandidate]] = {
        "hero/reference": [candidate for _, candidate in heroes],
        "ordinary building": [candidate for candidate in slice_candidates if candidate.feature_type == "building" and candidate.id not in hero_ids],
        "road/intersection": [candidate for candidate in slice_candidates if candidate.feature_type == "road"],
        "walkway/pedestrian": [candidate for candidate in slice_candidates if candidate.feature_type == "walkway"],
        "environmental": [candidate for candidate in slice_candidates if candidate.feature_type in {"waterway", "water", "landuse"}],
    }
    existing_rows = {}
    if output_path.exists():
        existing_rows = {row.get("candidateId"): row for row in read_json(output_path).get("rows", [])}
    rows: list[dict[str, Any]] = []
    for category, quota in QUOTAS.items():
        if category == "hero/reference":
            ordered = by_category[category]
        else:
            ordered = sorted(
                by_category[category],
                key=lambda candidate: (
                    tuple(-value for value in _score(candidate, category, _registry_match(candidate, registry), hero_candidates, connectivity, core_ids)),
                    candidate.id,
                ),
            )
        selected = ordered[:quota]
        for candidate in selected:
            registry_id = _registry_match(candidate, registry)
            hero_display = next((display for display, hero in heroes if hero.id == candidate.id), None)
            rows.append(_row(candidate, category, registry_id, hero_display, _score(candidate, category, registry_id, hero_candidates, connectivity, core_ids), existing_rows.get(candidate.id)))
    rows.sort(key=lambda row: (list(QUOTAS).index(row["category"]), row["candidateId"]))
    counts = {category: sum(row["category"] == category for row in rows) for category in QUOTAS}
    package = {
        "version": 1,
        "lifecycle": "human-review",
        "generatedAt": generated_at,
        "areaSource": area_path.relative_to(ROOT).as_posix() if area_path.is_relative_to(ROOT) else area_path.as_posix(),
        "candidateSource": candidate_path.relative_to(ROOT).as_posix() if candidate_path.is_relative_to(ROOT) else candidate_path.as_posix(),
        "sourceHash": payload.get("sourceHash"),
        "candidateCount": len(candidates),
        "sliceCandidateCount": len(slice_candidates),
        "requiredHeroes": [display for display, _ in HERO_SPECS],
        "missingRequiredHeroes": missing_heroes,
        "quotas": QUOTAS,
        "counts": counts,
        "priorityStatus": "pass" if len(rows) == sum(QUOTAS.values()) and counts == QUOTAS else "fail",
        "humanReviewStatus": "pending" if any(row["currentDecision"] == "pending" for row in rows) else "complete",
        "rows": rows,
    }
    write_json(output_path, package)
    write_markdown(markdown_path, package)
    return package


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_markdown(path: Path, package: dict[str, Any]) -> None:
    lines = [
        "# Vertical Slice Feature Review",
        "",
        "This is the authoritative 25-row package for explicit human review. Candidate/provider records are not canonical merely because they appear here.",
        "",
        f"- Area source: `{package['areaSource']}`",
        f"- Candidate rows in source: `{package['candidateCount']}`; intersecting slice candidates: `{package['sliceCandidateCount']}`",
        f"- Source hash: `{package.get('sourceHash') or 'not recorded'}`",
        f"- Priority status: **{package['priorityStatus']}**; human review: **{package['humanReviewStatus']}**",
        f"- Missing required heroes: `{', '.join(package['missingRequiredHeroes']) if package['missingRequiredHeroes'] else 'none'}`",
        "",
        "Review each row for identity, geometry, aliases, provider IDs, source rights, and property-level verification. Use the machine-readable JSON for decisions and corrections.",
        "",
        "| # | Category | Candidate ID | Type | Name | Aliases | External IDs | Registry match | Geometry | Position | Area/length | Provenance | Confidence | Recommended action | Decision |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(package["rows"], 1):
        position = _compact(row["approximatePosition"]) if row["approximatePosition"] else "null"
        magnitude = row["areaOrLength"]
        magnitude_text = f"{magnitude['value']} {magnitude['unit']}"
        aliases = "; ".join(row["aliases"]) or "none"
        external_ids = _compact(row["externalIds"])
        provenance = "; ".join(row["provenance"]) or "none"
        confidence = _compact(row["confidence"])
        action = row["recommendedAction"].replace("|", "\\|")
        lines.append(
            f"| {index} | `{row['category']}` | `{row['candidateId']}` | `{row['featureType']}` | {row['name']} | `{aliases}` | `{external_ids}` | `{row['registryMatch'] or 'pending'}` | `{row['geometryStatus']}` | `{position}` | {magnitude_text} | `{provenance}` | `{confidence}` | {action} | **{row['currentDecision']}** |"
        )
    lines.extend(
        [
            "",
            "## Required decision record",
            "",
            "An accept/reject/modify action must retain provider IDs, source geometry, provenance, and append a review-history entry. No AI-generated research is treated as human review.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args()
    package = build_priority_package(args.candidates, args.area, args.registry, args.output, args.markdown, generated_at=args.generated_at)
    print(json.dumps({key: package[key] for key in ("priorityStatus", "humanReviewStatus", "counts", "missingRequiredHeroes")}, indent=2, sort_keys=True))
    return 0 if package["priorityStatus"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
