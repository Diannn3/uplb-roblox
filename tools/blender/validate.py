from __future__ import annotations

import math
from typing import Any


REQUIRED_HERO_NAMES = {"UPLB Oblation", "UPLB Freedom Park", "Charles Fuller Baker Memorial Hall", "Dioscoro L. Umali Hall", "University Library and Knowledge Center"}


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    objects = manifest.get("objects", [])
    ids = [obj.get("objectId") for obj in objects]
    if len(ids) != len(set(ids)):
        errors.append("duplicate object IDs")
    if any(not obj.get("candidateId", "").startswith("candidate:") for obj in objects):
        errors.append("missing candidate IDs")
    names = {obj.get("name") for obj in objects if obj.get("worldgenRole") == "hero"}
    missing = sorted(REQUIRED_HERO_NAMES - names)
    if missing:
        errors.append(f"missing required heroes: {missing}")
    for obj in objects:
        transform = obj.get("transformLocalMeters") or {}
        dimensions = obj.get("dimensionsMeters") or {}
        values = [*transform.values(), *dimensions.values()]
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            errors.append(f"non-finite transform/dimensions: {obj.get('objectId')}")
        if abs(float(transform.get("eastM", 0))) > 10_000 or abs(float(transform.get("northM", 0))) > 10_000:
            errors.append(f"absurd local coordinate: {obj.get('objectId')}")
        if any(float(value) < 0 for value in dimensions.values()):
            errors.append(f"negative dimensions: {obj.get('objectId')}")
        if obj.get("worldgenRole") in {"hero", "context-building"} and float(obj.get("heightM", 0)) <= 0:
            errors.append(f"non-positive building height: {obj.get('objectId')}")
    return {"status": "pass" if not errors else "fail", "errors": errors, "objectCount": len(objects), "requiredHeroesMissing": missing, "meshValidation": "not-run-blender-unavailable"}
