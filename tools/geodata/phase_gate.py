"""Emit the Phase 1 evidence-closure gate and stop before world generation.

The gate separates engineering correctness from human review, DEM rights, and
provider comparison status. A blocked Overture comparison is recorded
explicitly but does not by itself block an OSM-first greybox POC.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from .generate_luau import generate_luau
from .geometry import GeometryState, inspect_geometry
from .io import read_json, sha256, write_json
from .models import CanonicalFeature, SourceRecord, ValidationReport
from .osm import ingest_osm_candidates
from .schemas import validate_artifacts
from .transform import CoordinateTransform


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = ROOT / "data" / "canonical" / "features.geojson"
DEFAULT_REGISTRY = ROOT / "data" / "canonical" / "identity-registry.json"
DEFAULT_SOURCES = ROOT / "data" / "canonical" / "source-records.json"
DEFAULT_REVIEWS = ROOT / "data" / "canonical" / "review-decisions.json"
DEFAULT_PRIORITY_REVIEW = ROOT / "data" / "reviews" / "vertical-slice-review.json"
DEFAULT_APPROVED_PRIORITY_REVIEW = ROOT / "data" / "reviews" / "approved" / "vertical-slice-review-v1.json"
DEFAULT_GENERATED = ROOT / "src" / "Shared" / "Generated" / "CanonicalFeatures.lua"
DEFAULT_REVIEW_DOC = ROOT / "docs" / "reviews" / "VERTICAL_SLICE_FEATURE_REVIEW.md"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "geodata" / "osm-small.json"
DEFAULT_REPORT = ROOT / "data" / "canonical" / "phase1-hardening-report.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "PHASE1_HARDENING_REPORT.md"
DEFAULT_CLOSURE_REPORT = ROOT / "data" / "canonical" / "phase1-closure-report.json"
DEFAULT_CLOSURE_MARKDOWN = ROOT / "docs" / "PHASE1_CLOSURE_REPORT.md"

REQUIRED_REVIEW_CATEGORIES = {
    "hero/reference": 5,
    "ordinary building": 8,
    "road/intersection": 5,
    "walkway/pedestrian": 5,
    "environmental": 2,
}
VALID_VERIFICATION = {"unknown", "provisional", "source-supported", "human-reviewed", "verified", "conflicting"}


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
                verification_status=str(properties.get("verificationStatus", "unknown")),
                verification={str(key): str(value) for key, value in (properties.get("verification") or {}).items()},
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
                metadata=item.get("metadata"),
            )
        )
    return records


def _contains_internal_overture_import(root: Path) -> bool:
    for path in sorted((root / "tools" / "geodata").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "overturemaps.core":
                return True
            if isinstance(node, ast.Import) and any(alias.name == "overturemaps.core" for alias in node.names):
                return True
    return False


def _review_gate(priority_path: Path, approved_path: Path = DEFAULT_APPROVED_PRIORITY_REVIEW) -> tuple[bool, dict[str, Any], str]:
    if not priority_path.exists():
        return False, {"rows": 0, "counts": {}, "missingRequiredHeroes": []}, "priority review package is missing"
    package = read_json(priority_path)
    rows = package.get("rows", [])
    counts = {str(key): int(value) for key, value in (package.get("counts") or {}).items()}
    package_complete = bool(rows) and len(rows) == 25 and not package.get("missingRequiredHeroes")
    approved: dict[str, Any] = read_json(approved_path) if approved_path.exists() else {}
    approved_rows = approved.get("rows", [])
    hashes_match = (
        approved.get("sourcePackageHash") == f"sha256:{sha256(priority_path)}"
        and approved.get("sourceCandidateHash") == package.get("sourceHash")
    )
    approved_complete = (
        approved.get("reviewVersion") == "v1"
        and approved.get("approvalStatus") == "approved"
        and approved.get("reviewer")
        and len(approved_rows) == len(rows) == 25
        and all(row.get("currentDecision") in {"accept", "reject"} and row.get("reviewStatus") == "reviewed" for row in approved_rows)
        and not approved.get("missingRequiredHeroes")
        and hashes_match
    )
    details = f"rows={len(rows)} counts={counts} missingHeroes={len(package.get('missingRequiredHeroes', []))} approvedRows={len(approved_rows)} approved={approved_complete}"
    package["approvedReview"] = {
        "path": approved_path.relative_to(ROOT).as_posix() if approved_path.is_relative_to(ROOT) else approved_path.as_posix(),
        "reviewVersion": approved.get("reviewVersion"),
        "approvalStatus": approved.get("approvalStatus"),
        "reviewer": approved.get("reviewer"),
        "sourcePackageHashMatches": hashes_match,
    }
    return package_complete and approved_complete, package, details


def _source_status(sources: list[SourceRecord], fragment: str) -> SourceRecord | None:
    return next((source for source in sources if fragment in source.id), None)


def build_gate(
    *,
    canonical_path: Path = DEFAULT_CANONICAL,
    registry_path: Path = DEFAULT_REGISTRY,
    sources_path: Path = DEFAULT_SOURCES,
    reviews_path: Path = DEFAULT_REVIEWS,
    priority_review_path: Path = DEFAULT_PRIORITY_REVIEW,
    approved_priority_review_path: Path = DEFAULT_APPROVED_PRIORITY_REVIEW,
    generated_path: Path = DEFAULT_GENERATED,
    review_doc_path: Path = DEFAULT_REVIEW_DOC,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> ValidationReport:
    report = ValidationReport(
        id="validation:phase1-closure-v1",
        input_revisions={
            "canonical": canonical_path.relative_to(ROOT).as_posix() if canonical_path.is_relative_to(ROOT) else canonical_path.as_posix(),
            "identityRegistry": registry_path.relative_to(ROOT).as_posix() if registry_path.is_relative_to(ROOT) else registry_path.as_posix(),
            "generated": generated_path.relative_to(ROOT).as_posix() if generated_path.is_relative_to(ROOT) else generated_path.as_posix(),
            "priorityReview": priority_review_path.relative_to(ROOT).as_posix() if priority_review_path.is_relative_to(ROOT) else priority_review_path.as_posix(),
            "approvedPriorityReview": approved_priority_review_path.relative_to(ROOT).as_posix() if approved_priority_review_path.is_relative_to(ROOT) else approved_priority_review_path.as_posix(),
        },
    )
    required_paths = (canonical_path, registry_path, sources_path, priority_review_path)
    if not all(path.exists() for path in required_paths):
        missing = [str(path) for path in required_paths if not path.exists()]
        report.blockers.append("missing required Phase 1 artifacts: " + ", ".join(missing))
        report.add_check("artifact-presence", "fail", "required canonical, registry, source, and review artifacts must exist")
        report.engineering_gate = "fail"
        report.finalize()
        return report

    features = _canonical_features(canonical_path)
    registry = read_json(registry_path)
    sources = _source_records(sources_path)
    report.measurements.update({"canonicalCount": len(features), "registryCount": len(registry.get("entities", {})), "sourceCount": len(sources)})

    provider_identity_leaks = [feature.id for feature in features if ":osm-" in feature.id or ":overture-" in feature.id or feature.id.startswith("candidate:")]
    duplicate_ids = len({feature.id for feature in features}) != len(features)
    missing_verification = [feature.id for feature in features if not feature.verification or any(value not in VALID_VERIFICATION for value in feature.verification.values())]
    registry_mismatches = [feature.id for feature in features if feature.id not in registry.get("entities", {})]
    report.add_check("candidate-canonical-separation", "pass" if all(feature.id.startswith("uplb:") for feature in features) else "fail", "canonical IDs are campus-domain IDs")
    report.add_check("persistent-identity-registry", "fail" if duplicate_ids or provider_identity_leaks or registry_mismatches else "pass", f"duplicates={duplicate_ids} providerIdentityLeaks={len(provider_identity_leaks)} registryMismatches={len(registry_mismatches)}")
    report.add_check("property-level-verification", "fail" if missing_verification else "pass", f"missingOrInvalidMaps={len(missing_verification)}")

    geometry_states: dict[str, str] = {}
    rejected: list[str] = []
    needs_review: list[str] = []
    for feature in features:
        if feature.geometry is None:
            continue
        inspection = inspect_geometry(feature.geometry)
        geometry_states[feature.id] = inspection.state.value
        if inspection.state == GeometryState.REJECTED:
            rejected.append(feature.id)
        elif inspection.state == GeometryState.NEEDS_REVIEW:
            needs_review.append(feature.id)
    report.measurements["geometryStates"] = geometry_states
    report.add_check("canonical-geometry-validity", "fail" if rejected or needs_review else "pass", f"rejected={len(rejected)} needsReview={len(needs_review)}")

    fixture_result = ingest_osm_candidates(fixture_path)
    type_names = {feature.feature_type for feature in fixture_result.features}
    report.add_check("expanded-osm-layers", "pass" if {"building", "walkway", "waterway"}.issubset(type_names) else "fail", f"fixtureTypes={','.join(sorted(type_names))}")
    multipolygons = [feature for feature in fixture_result.features if feature.geometry and feature.geometry.get("type") in {"Polygon", "MultiPolygon"} and feature.properties.get("relationMembers")]
    report.add_check("osm-multipolygon-relations", "pass" if multipolygons else "fail", f"relationPolygons={len(multipolygons)}")

    report.add_check("overture-public-api", "fail" if _contains_internal_overture_import(ROOT) else "pass", "adapter and fallback use documented package entry points")
    overture_source = _source_status(sources, "overture")
    if overture_source and overture_source.status == "blocked":
        report.overture_comparison_gate = "blocked"
        report.add_check("overture-comparison-status", "pass", "provider is explicitly blocked/deferred; no coverage claim is made and OSM-first POC remains allowed")
    elif overture_source and overture_source.status in {"validated", "available"}:
        report.overture_comparison_gate = "pass"
        report.add_check("overture-comparison-status", "pass", "provider comparison source is available")
    else:
        report.overture_comparison_gate = "deferred"
        report.add_check("overture-comparison-status", "pass", "provider comparison is deferred; no coverage claim is made")

    dem_source = _source_status(sources, "dem:")
    if dem_source is None:
        report.dem_rights_gate = "pending"
        report.add_check("dem-rights", "fail", "baseline DEM source record is missing")
    elif dem_source.rights_status in {"open-redistributable", "open-attribution-required", "share-alike"} and dem_source.status in {"validated", "validated-fallback", "validated-comparison-input", "validated-selected-baseline", "available"}:
        report.dem_rights_gate = "pass"
        report.add_check("dem-rights", "pass", f"{dem_source.id} has a recorded usable rights status and endpoint metadata")
    elif dem_source.rights_status in {"restricted-do-not-ingest", "permission-required"}:
        report.dem_rights_gate = "fail"
        report.add_check("dem-rights", "fail", f"{dem_source.id} is restricted or permission-gated")
    else:
        report.dem_rights_gate = "pending"
        report.add_check("dem-rights", "warning", f"{dem_source.id} rights remain unresolved")

    generated = generate_luau(features, CoordinateTransform(), sha256(canonical_path))
    generated_match = generated_path.exists() and generated_path.read_text(encoding="utf-8") == generated
    report.add_check("generated-luau-freshness", "pass" if generated_match else "fail", f"path={generated_path}")
    report.add_check("generated-determinism", "pass" if generate_luau(features, CoordinateTransform(), sha256(canonical_path)) == generated else "fail", "two in-memory generations compare equal")

    review_complete, package, review_details = _review_gate(priority_review_path, approved_priority_review_path)
    report.measurements["reviewPackage"] = {
        "rows": len(package.get("rows", [])),
        "counts": package.get("counts", {}),
        "missingRequiredHeroes": package.get("missingRequiredHeroes", []),
        "priorityStatus": package.get("priorityStatus"),
        "humanReviewStatus": "complete" if review_complete else package.get("humanReviewStatus"),
        "workingPackageHumanReviewStatus": package.get("humanReviewStatus"),
        "approvedReview": package.get("approvedReview", {}),
    }
    package_ok = len(package.get("rows", [])) == sum(REQUIRED_REVIEW_CATEGORIES.values()) and package.get("counts") == REQUIRED_REVIEW_CATEGORIES and package.get("priorityStatus") == "pass"
    report.add_check("priority-review-package", "pass" if package_ok else "fail", review_details)
    report.add_check("human-review-gate", "pass" if review_complete else "warning", "approved v1 review snapshot is complete and hash-bound" if review_complete else "approved v1 review snapshot with provenance is required before worldgen")

    artifact_errors = validate_artifacts(ROOT)
    report.add_check("schema-artifact-validation", "fail" if artifact_errors else "pass", "; ".join(artifact_errors[:3]) if artifact_errors else "canonical, source, registry, and review artifacts validate")

    failing_checks = {check["name"] for check in report.checks if check["status"] == "fail"}
    report.engineering_gate = "fail" if failing_checks else "pass"
    report.canonical_identity_gate = "pass" if not duplicate_ids and not provider_identity_leaks and not registry_mismatches and not missing_verification else "fail"
    report.geometry_gate = "pass" if not rejected and not needs_review else "fail"
    report.reproducibility_gate = "pass" if generated_match and not any(check["name"] == "generated-determinism" and check["status"] == "fail" for check in report.checks) else "fail"
    report.human_review_gate = "pass" if review_complete else "pending"
    report.worldgen_ready = all(
        gate == "pass"
        for gate in (report.engineering_gate, report.canonical_identity_gate, report.geometry_gate, report.reproducibility_gate, report.human_review_gate, report.dem_rights_gate)
    )
    report.campus_wide_production_ready = False
    report.hard_blockers = []
    for check in report.checks:
        if check["status"] == "fail":
            report.hard_blockers.append(f"{check['name']}: {check.get('details', 'failed')}")
    if report.human_review_gate != "pass":
        report.hard_blockers.append("required vertical-slice human review is incomplete")
    if report.dem_rights_gate != "pass":
        report.hard_blockers.append("baseline DEM rights are unresolved")
    report.deferred_enhancements = []
    if report.overture_comparison_gate in {"blocked", "deferred"}:
        report.deferred_enhancements.append("Overture comparison is unavailable; continue OSM-first without a coverage claim")
    report.deferred_enhancements.append("Optional secondary provider comparison remains deferred")
    report.campus_wide_blockers = [
        "Official UPLB GIS/licensing not acquired",
        "High-resolution LiDAR/terrain not acquired",
        "Campus-wide visual verification incomplete",
    ]
    report.blockers = list(report.hard_blockers)
    report.worldgen_ready = report.worldgen_ready and not report.hard_blockers
    report.measurements["overture"] = {"status": overture_source.status if overture_source else "not-recorded", "comparisonGate": report.overture_comparison_gate, "pinnedRelease": "2026-06-17.0"}
    report.finalize()
    if report.worldgen_ready:
        report.decision = "PASS_FOR_POC"
    elif report.hard_blockers:
        report.decision = "fail"
    else:
        report.decision = "NOT_READY_FOR_CAMPUS_WIDE_PRODUCTION"
    return report


def write_markdown(path: Path, report: ValidationReport) -> None:
    gates = {
        "engineeringGate": report.engineering_gate,
        "canonicalIdentityGate": report.canonical_identity_gate,
        "geometryGate": report.geometry_gate,
        "reproducibilityGate": report.reproducibility_gate,
        "humanReviewGate": report.human_review_gate,
        "demRightsGate": report.dem_rights_gate,
        "overtureComparisonGate": report.overture_comparison_gate,
        "worldgenReady": report.worldgen_ready,
        "campusWideProductionReady": report.campus_wide_production_ready,
    }
    lines = [
        "# Phase 1 Evidence Closure Report",
        "",
        f"**Decision:** `{report.decision}`",
        "",
        "`PASS_FOR_POC` means the evidence and engineering gates are sufficient for a controlled greybox proof of concept. It does not mean the campus is ready for production-wide reconstruction.",
        "",
        "",
        "This report is the fail-closed boundary before terrain, Blender, Roblox, or persistent world-generation work.",
        "",
        "## Gate status",
        "",
        "| Gate | Status |",
        "| --- | --- |",
        *[f"| `{key}` | **{value}** |" for key, value in gates.items()],
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
    hard_blocker_lines = [f"- {blocker}" for blocker in report.hard_blockers] or ["- none"]
    deferred_lines = [f"- {item}" for item in report.deferred_enhancements] or ["- none"]
    campus_lines = [f"- {item}" for item in report.campus_wide_blockers] or ["- none"]
    lines.extend(["## Hard blockers", "", *hard_blocker_lines, "", "## Deferred enhancements", "", *deferred_lines, "", "## Campus-wide blockers", "", *campus_lines, ""])
    lines.extend(["## Stop rule", "", "Do not start terrain, Blender, or Roblox world generation while `worldgenReady` is `false`. Overture comparison may remain blocked/deferred without blocking the OSM-first greybox POC.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--priority-review", type=Path, default=DEFAULT_PRIORITY_REVIEW)
    parser.add_argument("--approved-priority-review", type=Path, default=DEFAULT_APPROVED_PRIORITY_REVIEW)
    parser.add_argument("--generated", type=Path, default=DEFAULT_GENERATED)
    parser.add_argument("--review-doc", type=Path, default=DEFAULT_REVIEW_DOC)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", type=Path, default=DEFAULT_CLOSURE_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_CLOSURE_MARKDOWN)
    args = parser.parse_args()
    report = build_gate(canonical_path=args.canonical, registry_path=args.registry, sources_path=args.sources, reviews_path=args.reviews, priority_review_path=args.priority_review, approved_priority_review_path=args.approved_priority_review, generated_path=args.generated, review_doc_path=args.review_doc, fixture_path=args.fixture)
    write_json(args.json, report.to_dict())
    write_markdown(args.markdown, report)
    if args.json != DEFAULT_REPORT:
        write_json(DEFAULT_REPORT, report.to_dict())
    if args.markdown != DEFAULT_MARKDOWN:
        write_markdown(DEFAULT_MARKDOWN, report)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.decision != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
