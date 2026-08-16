"""Fail-closed validation for canonical data and evidence inputs."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import CanonicalFeature, SourceRecord, ValidationReport


def validate_features(
    features: Iterable[CanonicalFeature],
    source_records: Iterable[SourceRecord],
    input_revisions: dict[str, object],
) -> ValidationReport:
    feature_list = list(features)
    sources = {source.id: source for source in source_records}
    report = ValidationReport("validation:canonical-campus-v1", input_revisions)

    ids = [feature.id for feature in feature_list]
    duplicate_ids = [feature_id for feature_id, count in Counter(ids).items() if count > 1]
    report.add_check(
        "stable-feature-ids",
        "fail" if duplicate_ids or any(not feature_id.startswith("uplb:") for feature_id in ids) else "pass",
        "Duplicate or non-uplb IDs: " + ", ".join(duplicate_ids) if duplicate_ids else "All IDs are stable uplb:* identifiers.",
    )

    missing_provenance = [feature.id for feature in feature_list if not feature.provenance]
    unknown_sources = [
        feature.id
        for feature in feature_list
        if any(source_id not in sources for source_id in feature.provenance)
    ]
    report.add_check(
        "provenance-completeness",
        "fail" if missing_provenance or unknown_sources else "pass",
        f"missing={len(missing_provenance)} unknown={len(unknown_sources)}",
    )

    invalid_geometry = [
        feature.id
        for feature in feature_list
        if feature.geometry is not None and feature.geometry.get("type") not in {"Point", "LineString", "Polygon", "MultiPolygon", "MultiLineString"}
    ]
    report.add_check(
        "geojson-geometry-types",
        "fail" if invalid_geometry else "pass",
        f"invalid={len(invalid_geometry)}",
    )

    restricted = [
        source.id
        for source in sources.values()
        if source.rights_status in {"restricted-do-not-ingest", "permission-required", "uncertain"}
    ]
    report.add_check(
        "rights-gate",
        "warning" if restricted else "pass",
        "Restricted/uncertain sources are not permitted to silently enter canonical data: " + ", ".join(restricted),
    )
    report.measurements["featureCount"] = len(feature_list)
    report.measurements["featureTypes"] = dict(sorted(Counter(feature.feature_type for feature in feature_list).items()))
    report.finalize()
    return report
