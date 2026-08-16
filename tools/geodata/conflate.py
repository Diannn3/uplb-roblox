"""Projected, indexed candidate conflation with an explicit human-review queue."""

from __future__ import annotations

import re
import math
from typing import Iterable

from shapely.strtree import STRtree

from .geometry import area_m2, centroid_projected, iou, parse_geojson_geometry
from .identity import normalize_name, semantic_slug
from .models import CanonicalFeature, ConflationReview, ProviderCandidate


FeatureLike = CanonicalFeature | ProviderCandidate


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}


def _name_score(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _alias_match(left: FeatureLike, right: FeatureLike) -> float:
    left_names = {normalize_name(left.name), *(normalize_name(value) for value in left.aliases)}
    right_names = {normalize_name(right.name), *(normalize_name(value) for value in right.aliases)}
    left_names.discard("")
    right_names.discard("")
    if left_names & right_names:
        return 1.0
    return max((_name_score(a, b) for a in left_names for b in right_names), default=0.0)


def _provider(feature: FeatureLike) -> str:
    if isinstance(feature, ProviderCandidate):
        return feature.provider
    if "overture" in feature.external_ids:
        return "overture"
    if "osm" in feature.external_ids:
        return "osm"
    return "canonical"


def _external_candidate_id(feature: FeatureLike) -> str:
    if isinstance(feature, ProviderCandidate):
        return feature.id
    return feature.id


def _levels(feature: FeatureLike) -> float | None:
    value = feature.properties.get("levels")
    return float(value) if isinstance(value, (int, float)) else None


def _height(feature: FeatureLike) -> float | None:
    value = feature.properties.get("heightM")
    return float(value) if isinstance(value, (int, float)) else None


def _metrics(left: FeatureLike, right: FeatureLike) -> dict[str, float]:
    if not left.geometry or not right.geometry:
        return {
            "iou": 0.0,
            "centroidDistanceM": -1.0,
            "areaRatio": 0.0,
            "nameScore": _name_score(left.name, right.name),
            "aliasMatch": _alias_match(left, right),
        }
    left_area = area_m2(left.geometry)
    right_area = area_m2(right.geometry)
    levels_match = 0.0 if _levels(left) is None or _levels(right) is None else float(_levels(left) == _levels(right))
    left_height, right_height = _height(left), _height(right)
    height_diff = abs(left_height - right_height) if left_height is not None and right_height is not None else -1.0
    left_centroid = centroid_projected(left.geometry)
    right_centroid = centroid_projected(right.geometry)
    return {
        "iou": round(iou(left.geometry, right.geometry), 8),
        "centroidDistanceM": round(math.hypot(left_centroid[0] - right_centroid[0], left_centroid[1] - right_centroid[1]), 8),
        "areaRatio": round(min(left_area, right_area) / max(left_area, right_area), 8) if max(left_area, right_area) else 0.0,
        "nameScore": round(_name_score(left.name, right.name), 8),
        "aliasMatch": round(_alias_match(left, right), 8),
        "levelsMatch": levels_match,
        "heightDifferenceM": round(height_diff, 8),
    }


def _canonical_hint(osm: FeatureLike, overture: FeatureLike) -> str | None:
    semantic = semantic_slug("building", osm.name) or semantic_slug("building", overture.name)
    if semantic:
        return "uplb:" + semantic
    if isinstance(osm, CanonicalFeature) and osm.id.startswith("uplb:"):
        return osm.id
    if isinstance(overture, CanonicalFeature) and overture.id.startswith("uplb:"):
        return overture.id
    return None


def conflate_buildings(
    osm_features: Iterable[FeatureLike],
    overture_features: Iterable[FeatureLike],
    minimum_iou: float = 0.05,
) -> list[ConflationReview]:
    """Find plausible OSM/Overture pairs; every result remains pending."""

    osm = [feature for feature in osm_features if feature.feature_type == "building" and feature.geometry]
    overture = [feature for feature in overture_features if feature.feature_type == "building" and feature.geometry]
    if not osm or not overture:
        return []
    overture_shapes = [parse_geojson_geometry(feature.geometry) for feature in overture]
    tree = STRtree(overture_shapes)
    reviews: list[ConflationReview] = []
    for left in osm:
        left_shape = parse_geojson_geometry(left.geometry)
        for index in tree.query(left_shape):
            right = overture[int(index)]
            metrics = _metrics(left, right)
            if metrics["iou"] < minimum_iou and max(metrics["nameScore"], metrics["aliasMatch"]) < 0.25:
                continue
            recommendation = "probable-match" if metrics["iou"] >= 0.5 and max(metrics["nameScore"], metrics["aliasMatch"]) >= 0.25 else "possible-match"
            candidate_ids = {_provider(left): _external_candidate_id(left), _provider(right): _external_candidate_id(right)}
            reviews.append(
                ConflationReview(
                    id=f"review:building:{left.id.replace(':', '-')}--{right.id.replace(':', '-')}",
                    canonical_id=_canonical_hint(left, right),
                    candidate_ids=candidate_ids,
                    metrics=metrics,
                    recommendation=recommendation,
                    reason="Provider candidates overlap; human review is required before promotion or merge.",
                )
            )
    return sorted(reviews, key=lambda review: review.id)
