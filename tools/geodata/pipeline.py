"""Build candidates, promote only registry identities, and generate a slice handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .conflate import conflate_buildings
from .generate_luau import write_luau
from .geometry import select_intersecting
from .identity import IdentityRegistry
from .io import read_json, write_feature_collection, write_json
from .models import CanonicalFeature, ProviderCandidate, SourceRecord
from .osm import ingest_osm_candidates
from .overture import OvertureProvider
from .schemas import validate_schema_documents
from .transform import CoordinateTransform
from .validation import validate_features


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OSM = ROOT / "data" / "raw" / "osm_uplb_aoi.json"
DEFAULT_OUTPUT = ROOT / "data" / "canonical"
DEFAULT_FIXTURE = ROOT / "research" / "fixtures" / "uplb_reference_points.geojson"
DEFAULT_REGISTRY = ROOT / "data" / "canonical" / "identity-registry.json"
DEFAULT_AREA = ROOT / "data" / "areas" / "vertical-slice-v0.geojson"
DEFAULT_GENERATED = ROOT / "src" / "Shared" / "Generated" / "CanonicalFeatures.lua"
DEFAULT_REVIEW_DOC = ROOT / "docs" / "reviews" / "VERTICAL_SLICE_FEATURE_REVIEW.md"


def _reference_candidates(path: Path, source_id: str) -> list[ProviderCandidate]:
    result: list[ProviderCandidate] = []
    for item in read_json(path).get("features", []):
        properties = item.get("properties") or {}
        raw_id = str(properties.get("id", "reference"))
        external = properties.get("osm")
        result.append(
            ProviderCandidate(
                id=f"candidate:osm:{external or 'reference/' + raw_id}",
                provider="osm",
                feature_type="landmark",
                name=str(properties.get("name") or raw_id),
                geometry=item.get("geometry"),
                properties={"referenceConfidence": properties.get("confidence", "reference-only")},
                external_ids={"osm": str(external)} if external else {},
                provenance=(source_id,),
                confidence={"position": "medium", "footprint": "unknown", "height": "unknown", "facade": "unknown"},
            )
        )
    return result


def _blocked_overture_source(accessed_at: str) -> SourceRecord:
    return SourceRecord(
        id=f"source:overture:buildings@{accessed_at}",
        provider="Overture Maps Foundation",
        source_url="https://docs.overturemaps.org/guides/buildings/",
        accessed_at=accessed_at,
        license="ODbL-1.0",
        attribution="Overture Maps Foundation and upstream contributors",
        redistribution="allowed-with-conditions",
        rights_status="open-attribution-required",
        intended_use=("building-footprint", "building-height", "conflation-candidate"),
        status="blocked",
        notes=(
            "Provider access is blocked; no coverage conclusion is drawn.",
            "Attempted release: 2026-06-17.0; optional overturemaps package was not installed in this run.",
        ),
    )


def _dem_candidate_source(accessed_at: str) -> SourceRecord:
    return SourceRecord(
        id="source:dem:srtm-baseline",
        provider="NASA Earthdata LP DAAC",
        source_url="https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003",
        accessed_at=accessed_at,
        license="NASA Earthdata open data policy; SRTMGL1.003 is openly shared without restriction, with citation requested.",
        attribution="NASA JPL; NASA Land Processes Distributed Active Archive Center (LP DAAC)",
        redistribution="allowed; cite the DOI and do not imply NASA endorsement",
        rights_status="open-redistributable",
        intended_use=("30m-terrain-baseline",),
        status="validated-fallback",
        notes=("No raster is ingested in this evidence-foundation cycle.",),
        metadata={
            "productShortName": "SRTMGL1",
            "collectionVersion": "003",
            "resolution": "1 arc-second (~30 m posting)",
            "doi": "10.5067/MEASURES/SRTM/SRTMGL1.003",
            "landingPage": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003",
            "accessPath": "Earthdata Search/Earthdata Cloud supported path; no retired LP DAAC Data Pool endpoint",
            "crs": "EPSG:4326 geographic (1-degree HGT tiles)",
            "verticalUnits": "metres",
            "verticalDatum": "WGS84 ellipsoid referenced to EGM96 geoid",
            "nodata": "Version 3.0 has no voids; -32768 is historical Version 1/2.1 fill value",
            "authRequirement": "Earthdata Login required for download; no credentials stored",
        },
    )


def _area_geometry(area_path: Path) -> dict[str, Any]:
    payload = read_json(area_path)
    feature = next(feature for feature in payload.get("features", []) if feature.get("properties", {}).get("role") == "core")
    return feature["geometry"]


def _canonical_from_registry(candidate: ProviderCandidate, canonical_id: str, registry: IdentityRegistry) -> CanonicalFeature:
    entity = registry.entities[canonical_id]
    return CanonicalFeature(
        id=canonical_id,
        feature_type=entity["featureType"],
        name=entity["canonicalName"],
        geometry=candidate.geometry,
        aliases=tuple(entity.get("aliases", [])),
        properties=candidate.properties,
        external_ids=candidate.external_ids,
        provenance=candidate.provenance,
        confidence=candidate.confidence,
        verification_status=entity.get("identityStatus", "needs-review"),
        verification={str(key): str(value) for key, value in entity.get("verification", {}).items()},
    )


def _review_markdown(candidates: list[ProviderCandidate], registry: IdentityRegistry, area_path: Path) -> str:
    lines = [
        "# Vertical Slice Feature Review",
        "",
        "This package is pending human review. Candidate/provider records are not canonical merely because they appear here.",
        "",
        f"- Area source: `{area_path.as_posix()}`",
        f"- Candidate rows: `{len(candidates)}`",
        "- Review action: confirm identity, geometry, aliases, source rights, and verification status before promotion.",
        "",
        "| Candidate ID | Feature type | Name | External IDs | Registry match | Action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidates[:25]:
        registry_id = registry.resolve_or_allocate(candidate.feature_type, candidate.name, candidate.external_ids, promote=False) or "pending"
        external = "; ".join(f"{key}={value}" for key, value in sorted(candidate.external_ids.items())) or "none"
        lines.append(f"| `{candidate.id}` | `{candidate.feature_type}` | {candidate.name} | `{external}` | `{registry_id}` | pending human review |")
    lines.extend(["", "No feature in this document is automatically verified or promoted.", ""])
    return "\n".join(lines)


def select_vertical_slice(features: list[CanonicalFeature | ProviderCandidate], area_path: Path = DEFAULT_AREA) -> list[CanonicalFeature | ProviderCandidate]:
    return list(select_intersecting(features, _area_geometry(area_path), buffer_m=120))


def build(
    osm_path: Path,
    output_dir: Path,
    fixture_path: Path,
    accessed_at: str,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    area_path: Path = DEFAULT_AREA,
    generated_path: Path = DEFAULT_GENERATED,
    overture_path: Path | None = None,
    review_doc_path: Path | None = None,
) -> dict[str, Any]:
    schema_errors = validate_schema_documents()
    if schema_errors:
        raise RuntimeError("production schema bundle failed: " + "; ".join(schema_errors))
    osm_result = ingest_osm_candidates(osm_path, accessed_at)
    reference_candidates = _reference_candidates(fixture_path, osm_result.source.id)
    candidates = sorted([*osm_result.features, *reference_candidates], key=lambda feature: feature.id)
    candidate_root = output_dir.parent / "candidates"
    write_feature_collection(
        candidate_root / "osm" / "features.geojson",
        [feature.to_geojson_feature() for feature in candidates],
        lifecycle="candidate",
        provider="osm",
        sourceHash=osm_result.source.content_hash,
    )
    write_json(candidate_root / "osm" / "source-record.json", osm_result.source.to_dict())

    overture_candidates: tuple[ProviderCandidate, ...] = ()
    overture_source: dict[str, Any] | None = None
    if overture_path and overture_path.exists():
        overture_candidates, overture_source = OvertureProvider().normalize_geojson(overture_path, release="pinned-input")
        write_feature_collection(candidate_root / "overture" / "buildings.geojson", [feature.to_geojson_feature() for feature in overture_candidates], lifecycle="candidate", provider="overture")
        write_json(candidate_root / "overture" / "source-record.json", overture_source)

    registry = IdentityRegistry.load(registry_path)
    slice_candidates = select_vertical_slice(candidates, area_path)
    canonical_by_id: dict[str, CanonicalFeature] = {}
    for candidate in slice_candidates:
        canonical_id = registry.resolve_or_allocate(candidate.feature_type, candidate.name, candidate.external_ids, promote=False)
        if canonical_id and canonical_id not in canonical_by_id:
            canonical_by_id[canonical_id] = _canonical_from_registry(candidate, canonical_id, registry)
    canonical_features = sorted(canonical_by_id.values(), key=lambda feature: feature.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_feature_collection(
        output_dir / "features.geojson",
        [feature.to_geojson_feature() for feature in canonical_features],
        lifecycle="canonical",
        canonicalVersion="canonical-v1",
        areaSource=area_path.relative_to(ROOT).as_posix() if area_path.is_relative_to(ROOT) else area_path.as_posix(),
        candidateCount=len(candidates),
    )
    write_json(output_dir / "identity-registry.json", registry.to_dict())
    source_records = [osm_result.source, _blocked_overture_source(accessed_at), _dem_candidate_source(accessed_at)]
    write_json(output_dir / "source-records.json", {"sources": [source.to_dict() for source in source_records], "version": 1})
    reviews = conflate_buildings(osm_result.features, overture_candidates)
    write_json(output_dir / "review-decisions.json", {"version": 1, "decisions": [review.to_dict() for review in reviews]})
    write_json(output_dir / "conflation-reviews.json", {"version": 2, "reviews": [review.to_dict() for review in reviews]})
    report = validate_features(canonical_features, source_records, {"osm": osm_result.source.content_hash, "canonicalVersion": "canonical-v1"})
    report.measurements.update({"candidateCount": len(candidates), "canonicalCount": len(canonical_features), "sliceCandidateCount": len(slice_candidates), "pendingReviewCount": len(reviews)})
    write_json(output_dir / "validation-report.json", report.to_dict())
    write_luau(generated_path, canonical_features, CoordinateTransform(), output_dir / "features.geojson")
    if review_doc_path:
        review_doc_path.parent.mkdir(parents=True, exist_ok=True)
        review_doc_path.write_text(_review_markdown(slice_candidates, registry, area_path), encoding="utf-8", newline="\n")
    return {
        "candidateCount": len(candidates),
        "canonicalCount": len(canonical_features),
        "sliceCandidateCount": len(slice_candidates),
        "pendingReviewCount": len(reviews),
        "osmHash": osm_result.source.content_hash,
        "overtureSource": overture_source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--overture", type=Path)
    parser.add_argument("--accessed-at", default="2026-08-17")
    args = parser.parse_args()
    result = build(args.osm, args.output, args.fixture, args.accessed_at, registry_path=args.registry, area_path=args.area, overture_path=args.overture, review_doc_path=DEFAULT_REVIEW_DOC)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
