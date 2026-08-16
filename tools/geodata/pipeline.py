"""Build canonical UPLB data and the first vertical-slice handoff."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .conflate import conflate_buildings
from .generate_luau import write_luau
from .io import geometry_anchor, read_json, write_feature_collection, write_json
from .models import CanonicalFeature, SourceRecord
from .osm import ingest_osm
from .schemas import validate_schema_documents
from .transform import CoordinateTransform
from .validation import validate_features


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OSM = ROOT / "research" / "raw" / "osm_uplb_aoi.json"
DEFAULT_OUTPUT = ROOT / "data" / "canonical"
DEFAULT_FIXTURE = ROOT / "research" / "fixtures" / "uplb_reference_points.geojson"
VERTICAL_SLICE_BBOX = (121.238, 14.158, 121.2465, 14.1685)


def _reference_features(path: Path, source_id: str) -> list[CanonicalFeature]:
    features: list[CanonicalFeature] = []
    for item in read_json(path).get("features", []):
        properties = item.get("properties") or {}
        source_key = str(properties.get("id", "reference")).casefold()
        if source_key == "uplb-oblation":
            feature_id = "uplb:landmark:oblation"
        elif source_key == "freedom-park":
            feature_id = "uplb:landmark:freedom-park"
        else:
            feature_id = f"uplb:landmark:{source_key.replace('_', '-') }"
        features.append(
            CanonicalFeature(
                id=feature_id,
                feature_type="landmark",
                name=str(properties.get("name") or feature_id.rsplit(":", 1)[-1]),
                geometry=item.get("geometry"),
                properties={
                    "referenceConfidence": properties.get("confidence", "reference-only"),
                    "externalReference": properties.get("osm"),
                },
                external_ids={"osm": str(properties["osm"])} if properties.get("osm") else {},
                provenance=(source_id,),
                confidence={"position": "medium", "footprint": "unknown", "height": "unknown", "facade": "unknown"},
                verification_status="reference-only",
            )
        )
    return features


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
        notes=(
            "Provider access is currently blocked by STAC/catalog or direct-cloud availability; this is not a coverage claim.",
            "Adapter remains available for a later pinned extract.",
        ),
    )


def _dem_candidate_source(accessed_at: str) -> SourceRecord:
    return SourceRecord(
        id="source:dem:srtm-baseline",
        provider="NASA Earthdata LP DAAC",
        source_url="https://www.earthdata.nasa.gov/centers/lp-daac",
        accessed_at=accessed_at,
        license="Product-specific; endpoint and redistribution terms require verification.",
        redistribution="not-yet-verified",
        rights_status="uncertain",
        intended_use=("30m-terrain-baseline",),
        notes=("Fallback candidate only; no raster is ingested until the license gate passes.",),
    )


def _in_vertical_slice(feature: CanonicalFeature) -> bool:
    anchor = geometry_anchor(feature.geometry)
    if anchor is None:
        return False
    west, south, east, north = VERTICAL_SLICE_BBOX
    return west <= anchor[0] <= east and south <= anchor[1] <= north


def select_vertical_slice(features: list[CanonicalFeature]) -> list[CanonicalFeature]:
    allowed = {"building", "road", "walkway", "waterway", "poi", "landmark"}
    selected = [feature for feature in features if feature.feature_type in allowed and _in_vertical_slice(feature)]
    required = {"uplb:landmark:oblation", "uplb:landmark:freedom-park", "uplb:building:baker-hall"}
    by_id = {feature.id: feature for feature in selected}
    for feature in features:
        if feature.id in required:
            by_id[feature.id] = feature
    return sorted(by_id.values(), key=lambda feature: feature.id)


def build(osm_path: Path, output_dir: Path, fixture_path: Path, accessed_at: str) -> dict[str, Any]:
    schema_errors = validate_schema_documents()
    if schema_errors:
        raise RuntimeError("production schema bundle failed: " + "; ".join(schema_errors))
    osm_result = ingest_osm(osm_path, accessed_at)
    references = _reference_features(fixture_path, osm_result.source.id)
    combined: dict[str, CanonicalFeature] = {feature.id: feature for feature in osm_result.features}
    for feature in references:
        combined.setdefault(feature.id, feature)
    features = sorted(combined.values(), key=lambda feature: feature.id)
    source_records = [osm_result.source, _blocked_overture_source(accessed_at), _dem_candidate_source(accessed_at)]

    output_dir.mkdir(parents=True, exist_ok=True)
    feature_collection = [feature.to_geojson_feature() for feature in features]
    canonical_path = output_dir / "features.geojson"
    write_feature_collection(
        canonical_path,
        feature_collection,
        canonicalVersion="canonical-v1",
        coordinateReferenceSystem="EPSG:4326",
        sourcePolicy="OSM-first; Overture adapter remains review-only while blocked",
    )
    write_json(output_dir / "source-records.json", {"version": 1, "sources": [source.to_dict() for source in source_records]})

    reviews = conflate_buildings(features, [])
    write_json(output_dir / "conflation-reviews.json", {"version": 1, "reviews": [review.to_dict() for review in reviews]})
    report = validate_features(
        features,
        source_records,
        {"osm": osm_result.source.content_hash, "canonicalVersion": "canonical-v1"},
    )
    report.measurements["skippedOsmElements"] = osm_result.skipped_elements
    write_json(output_dir / "validation-report.json", report.to_dict())

    slice_features = select_vertical_slice(features)
    write_feature_collection(
        output_dir / "vertical-slice.geojson",
        [feature.to_geojson_feature() for feature in slice_features],
        canonicalVersion="canonical-v1",
        coordinateReferenceSystem="EPSG:4326",
        verticalSliceBBox=list(VERTICAL_SLICE_BBOX),
        requiredFeatureIds=[
            "uplb:landmark:oblation",
            "uplb:landmark:freedom-park",
            "uplb:building:baker-hall",
        ],
    )
    write_luau(
        ROOT / "src" / "Shared" / "Generated" / "CanonicalFeatures.lua",
        slice_features,
        CoordinateTransform(),
        canonical_path,
    )
    return {
        "featureCount": len(features),
        "verticalSliceCount": len(slice_features),
        "skippedOsmElements": osm_result.skipped_elements,
        "osmHash": osm_result.source.content_hash,
        "requiredFeatureIds": [
            feature_id
            for feature_id in (
                "uplb:landmark:oblation",
                "uplb:landmark:freedom-park",
                "uplb:building:baker-hall",
            )
            if feature_id in {feature.id for feature in slice_features}
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--accessed-at", default="2026-08-17")
    args = parser.parse_args()
    result = build(args.osm, args.output, args.fixture, args.accessed_at)
    import json

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
