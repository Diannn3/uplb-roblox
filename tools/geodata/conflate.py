"""Conservative candidate matching without a heavyweight GIS dependency."""

from __future__ import annotations

import re
from typing import Iterable

from .io import geometry_bbox
from .models import CanonicalFeature, ConflationReview


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}


def _bbox_iou(left: tuple[float, float, float, float] | None, right: tuple[float, float, float, float] | None) -> float:
    if not left or not right:
        return 0.0
    west = max(left[0], right[0])
    south = max(left[1], right[1])
    east = min(left[2], right[2])
    north = min(left[3], right[3])
    intersection = max(0.0, east - west) * max(0.0, north - south)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def conflate_buildings(
    canonical: Iterable[CanonicalFeature],
    candidates: Iterable[CanonicalFeature],
    minimum_iou: float = 0.15,
) -> list[ConflationReview]:
    """Emit review records for plausible matches; never auto-merge geometry."""

    canonical_buildings = [feature for feature in canonical if feature.feature_type == "building"]
    candidate_buildings = [feature for feature in candidates if feature.feature_type == "building"]
    reviews: list[ConflationReview] = []
    for candidate in candidate_buildings:
        candidate_tokens = _tokens(candidate.name)
        matches: list[dict[str, object]] = []
        for target in canonical_buildings:
            iou = _bbox_iou(geometry_bbox(candidate.geometry), geometry_bbox(target.geometry))
            name_overlap = len(candidate_tokens & _tokens(target.name))
            if iou >= minimum_iou or name_overlap >= 1:
                matches.append(
                    {
                        "canonicalId": target.id,
                        "iou": round(iou, 8),
                        "nameOverlap": name_overlap,
                    }
                )
        matches.sort(key=lambda match: (-float(match["iou"]), -int(match["nameOverlap"]), str(match["canonicalId"])))
        if matches:
            reviews.append(
                ConflationReview(
                    id=f"review:building:{candidate.id.split(':')[-1]}",
                    canonical_id=str(matches[0]["canonicalId"]),
                    candidates=tuple(matches),
                    reason="Candidate overlap/name match requires human review; no automatic merge is performed.",
                )
            )
    return reviews
