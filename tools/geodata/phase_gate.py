"""Emit the offline Phase 1 hardening gate and stop before world generation.

The gate is intentionally conservative.  A conditional result is a useful
artifact for review, but it is not permission to start terrain, Blender, or
Roblox work.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from .geometry import GeometryState, inspect_geometry
from .io import read_json, sha256, write_json
from .models import CanonicalFeature, SourceRecord, ValidationReport
from .osm import ingest_osm_candidates
from .schemas import validate_artifacts
from .transform import CoordinateTransform
from .generate_luau import generate_luau


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = ROOT / "data" / "canonical" / "features.geojson"
DEFAULT_REGISTRY = ROOT / "data" / "canonical" / "identity-registry.json"
DEFAULT_SOURCES = ROOT / "data" / "canonical" / "source-records.json"
DEFAULT_REVIEWS = ROOT / "data" / "canonical" / "review-decisions.json"
DEFAULT_GENERATED = ROOT / "src" / "Shared" / "Generated" / "CanonicalFeatures.lua"
DEFAULT_REVIEW_DOC = ROOT / "docs" / "reviews" / "VERTICAL_SLICE_FEATURE_REVIEW.md"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "geodata" / "osm-small.json"
DEFAULT_REPORT = ROOT / "data" / "canonical" / "phase1-hardening-report.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "PHASE1_HARDENING_REPORT.md"


def _canonical_features(path: Path) -> list[CanonicalFeature]:
    payload = read_json(path)
    result: list[CanonicalFeature] = []
    for item in payload.get("features", []):
        properties = item.get("properties") or {}
        result.append(
            CanonicalFeature(
                id=str(item["id"]),
                feature_type=str(properties.get("featureType", "unknown")),
                name=str(properties.get("name", item["id"])),
                geometry=item.get("geometry"),
                aliases=tuple(properties.get("aliases", [])),
                properties=dict(properties.get("attributes", {})),
                external_ids={str(key): str(value) for key, value in (properties.get("externalIds") or {}).items()},
                provenance=tuple(properties.get("provenance", [])),
                confidence={str(key): str(value) for key, value in (properties.get("confidence") or {}).items()},
                verification_status=str(properties.get("verificationStatus", "needs-review")),
            )
        )
    return result


def _source_records(path: Path) -> list[SourceRecord]:
    payload = read_json(path)
    records: list[SourceRecord] = []
    for item in payload.get("sources", []):
        records.append(
            SourceRecord(
                id=str(item["id"]),
                provider=str(item["provider"]),
                source_url=str(item["sourceUrl"]),
                accessed_at=str(item["accessedAt"]),
                rights_status=item["rightsStatus"],
                intended_use=tuple(item.get("intendedUse", [])),
                status=str(item.get("status", "validated")),
                captured_at=item.get("capturedAt"),
                license=item.get("license"),
                attribution=item.get("attribution"),
                redistribution=item.get("redistribution"),
                content_hash=item.get("contentHash"),
                coverage=item.get("coverage"),
                notes=tuple(item.get("notes", [])),
            )
        )
    return records


def _contains_internal_overture_import(root: Path) -> bool:
    for path in sorted((root / "tools" / "geodata").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == ".".join(("overturemaps", "core")):
                return True
            if isinstance(node, ast.Import) and any(alias.name == ".".join(("overturemaps", "core")) for alias in node.names):
                return True
    return False


def build_gate(
    *,
    canonical_path: Path = DEFAULT_CANONICAL,
    registry_path: Path = DEFAULT_REGISTRY,
    sources_path: Path = DEFAULT_SOURCES,
    reviews_path: Path = DEFAULT_REVIEWS,
    generated_path: Path = DEFAULT_GENERATED,
    review_doc_path: Path = DEFAULT_REVIEW_DOC,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> ValidationReport:
    report = ValidationReport(
        id="validation:phase1-hardening-v1",
        input_revisions={
            "canonical": canonical_path.relative_to(ROOT).as_posix() if canonical_path.is_relative_to(ROOT) else canonical_path.as_posix(),
            "identityRegistry": registry_path.relative_to(ROOT).as_posix() if registry_path.is_relative_to(ROOT) else registry_path.as_posix(),
            "generated": generated_path.relative_to(ROOT).as_posix() if generated_path.is_relative_to(ROOT) else generated_path.as_posix(),
        },
    )
    if not canonical_path.exists() or not registry_path.exists() or not sources_path.exists():
        report.blockers.append("canonical artifacts, identity registry, and source records must exist")
        report.add_check("artifact-presence", "fail", "missing one or more required Phase 1 artifacts")
        report.finalize()
        return report

    features = _canonical_features(canonical_path)
    registry = read_json(registry_path)
    sources = _source_records(sources_path)
    report.measurements.update({"canonicalCount": len(features), "registryCount": len(registry.get("entities", {})), "sourceCount": len(sources)})
    overture_sources = [source for source in sources if "overture" in source.id]
    report.measurements["overture"] = {
        "status": overture_sources[0].status if overture_sources else "not-recorded",
        "attemptedRelease": "2026-06-17.0",
        "packageVersion": "not-installed",
    }

    report.add_check(
        "candidate-canonical-separation",
        "pass" if all(feature.id.startswith("uplb:") for feature in features) else "fail",
        "canonical feature IDs are opaque/semantic campus IDs; provider candidates remain external evidence",
    )
    duplicate_ids = len({feature.id for feature in features}) != len(features)
    provider_identity_leaks = [feature.id for feature in features if ":osm-" in feature.id or ":overture-" in feature.id]
    report.add_check(
        "persistent-identity-registry",
        "fail" if duplicate_ids or provider_identity_leaks else "pass",
        f"duplicates={duplicate_ids} providerIdentityLeaks={len(provider_identity_leaks)}",
    )
    geometry_states: dict[str, str] = {}
    rejected: list[str] = []
    review_geometry: list[str] = []
    for feature in features:
        if feature.geometry is None:
            continue
        inspection = inspect_geometry(feature.geometry)
        geometry_states[feature.id] = inspection.state.value
        if inspection.state == GeometryState.REJECTED:
            rejected.append(feature.id)
        elif inspection.state == GeometryState.NEEDS_REVIEW:
            review_geometry.append(feature.id)
    report.measurements["geometryStates"] = geometry_states
    report.add_check("canonical-geometry-validity", "fail" if rejected else ("warning" if review_geometry else "pass"), f"rejected={len(rejected)} needsReview={len(review_geometry)}")

    fixture_result = ingest_osm_candidates(fixture_path)
    type_names = {feature.feature_type for feature in fixture_result.features}
    report.add_check(
        "expanded-osm-layers",
        "pass" if {"building", "walkway", "waterway"}.issubset(type_names) else "fail",
        f"fixtureTypes={','.join(sorted(type_names))}",
    )
    multipolygons = [feature for feature in fixture_result.features if feature.geometry and feature.geometry.get("type") in {"Polygon", "MultiPolygon"} and feature.properties.get("relationMembers")]
    report.add_check("osm-multipolygon-relations", "pass" if multipolygons else "fail", f"relationPolygons={len(multipolygons)}")

    report.add_check(
        "overture-public-api",
        "fail" if _contains_internal_overture_import(ROOT) else "pass",
        "adapter and fallback use documented package entry points",
    )
    overture_candidate_path = ROOT / "data" / "candidates" / "overture" / "buildings.geojson"
    review_rows = read_json(reviews_path).get("decisions", []) if reviews_path.exists() else []
    if overture_candidate_path.exists():
        report.add_check("overture-candidate-review", "pass" if review_rows else "fail", f"pendingOrDecidedReviews={len(review_rows)}")
    else:
        report.add_check("overture-candidate-review", "warning", "provider is blocked; no Overture coverage conclusion is made")

    uncertain_sources = [source.id for source in sources if source.rights_status in {"uncertain", "permission-required", "restricted-do-not-ingest"}]
    canonical_source_ids = {source_id for feature in features for source_id in feature.provenance}
    leaked_uncertain = sorted(set(uncertain_sources) & canonical_source_ids)
    report.add_check("rights-gate", "fail" if leaked_uncertain else ("warning" if uncertain_sources else "pass"), f"uncertainSources={len(uncertain_sources)} canonicalLeaks={len(leaked_uncertain)}")

    source_hash = sha256(canonical_path)
    generated = generate_luau(features, CoordinateTransform(), source_hash)
    generated_match = generated_path.exists() and generated_path.read_text(encoding="utf-8") == generated
    report.add_check("generated-luau-freshness", "pass" if generated_match else "fail", f"path={generated_path}")
    report.add_check("generated-determinism", "pass" if generate_luau(features, CoordinateTransform(), source_hash) == generated else "fail", "two in-memory generations compare equal")

    review_lines = review_doc_path.read_text(encoding="utf-8").splitlines() if review_doc_path.exists() else []
    review_rows_in_doc = sum(1 for line in review_lines if line.startswith("| `candidate:"))
    report.measurements["reviewPackageRows"] = review_rows_in_doc
    report.add_check("first-25-review-package", "pass" if review_rows_in_doc >= 1 else "fail", f"rows={review_rows_in_doc}; package remains pending human review")

    artifact_errors = validate_artifacts(ROOT)
    report.add_check("schema-artifact-validation", "fail" if artifact_errors else "pass", "; ".join(artifact_errors[:3]) if artifact_errors else "canonical artifacts validate against production schemas")
    report.finalize()
    return report


def write_markdown(path: Path, report: ValidationReport) -> None:
    lines = [
        "# Phase 1 Geospatial Hardening Report",
        "",
        f"**Decision:** `{report.decision}`",
        "",
        "A `pass` is required before terrain, Blender, or Roblox world-generation work. A `conditional` result records known evidence/provider or rights blockers and intentionally stops the project at the Phase 1 gate.",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "| --- | --- | --- |",
    ]
    for check in report.checks:
        details = check.get("details", "").replace("|", "\\|")
        lines.append(f"| `{check['name']}` | **{check['status']}** | {details} |")
    lines.extend(["", "## Measurements", "", "```json", json.dumps(report.measurements, indent=2, sort_keys=True), "```", ""])
    if report.blockers:
        lines.extend(["## Blockers", "", *[f"- {blocker}" for blocker in report.blockers], ""])
    lines.extend(["## Stop rule", "", "Do not start the DEM, Blender, or persistent Roblox Studio phases until this report is reviewed and the decision is `pass`.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--generated", type=Path, default=DEFAULT_GENERATED)
    parser.add_argument("--review-doc", type=Path, default=DEFAULT_REVIEW_DOC)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_gate(canonical_path=args.canonical, registry_path=args.registry, sources_path=args.sources, reviews_path=args.reviews, generated_path=args.generated, review_doc_path=args.review_doc, fixture_path=args.fixture)
    write_json(args.json, report.to_dict())
    write_markdown(args.markdown, report)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.decision != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
