from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


CAPABILITIES = {
    "identity",
    "footprint",
    "height",
    "levels",
    "facade",
    "orientation",
    "roof",
    "materials",
    "interior",
    "historical-state",
    "geometry",
    "landscaping",
}

CONFIDENCE_LEVELS = {
    "unknown",
    "low",
    "medium-low",
    "medium",
    "medium-high",
    "high",
    "source-supported",
    "field-measured",
}

RIGHTS_STATUSES = {
    "project-canonical-provenance",
    "open-cc-by-sa",
    "open-cc-by",
    "public-domain",
    "reference-only-permission-required",
    "metadata-reference-only",
    "institutional-consultation-required",
    "unknown-review-required",
}


class EvidenceError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_schema(document: dict[str, Any], schema_path: Path, label: str = "document") -> None:
    schema = read_json(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda err: list(err.absolute_path))
    if errors:
        rendered = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors
        )
        raise EvidenceError(f"{label} schema failure: {rendered}")


def validate_reference_profile_v02(profile: dict[str, Any]) -> dict[str, Any]:
    source_rows = profile.get("sources", [])
    source_ids = [row.get("id") for row in source_rows]
    if len(source_ids) != len(set(source_ids)):
        raise EvidenceError("reference profile contains duplicate source IDs")
    sources = {row["id"]: row for row in source_rows}

    errors: list[str] = []
    warnings: list[str] = []
    for source in source_rows:
        rights = source.get("rightsStatus")
        if rights not in RIGHTS_STATUSES:
            errors.append(f"{source.get('id')}: unsupported rightsStatus {rights!r}")
        capabilities = set(source.get("evidenceCapabilities", []))
        unknown = sorted(capabilities - CAPABILITIES)
        if unknown:
            errors.append(f"{source.get('id')}: unsupported capabilities {unknown}")
        if source.get("kind") not in {"canonical-geodata", "project-generated"} and not source.get("sourceUri"):
            warnings.append(f"{source.get('id')}: external/reference source has no sourceUri")

    observation_ids: set[str] = set()
    for observation in profile.get("observations", []):
        observation_id = str(observation.get("id"))
        if observation_id in observation_ids:
            errors.append(f"duplicate observation ID {observation_id}")
        observation_ids.add(observation_id)
        capability = observation.get("capability")
        if capability not in CAPABILITIES:
            errors.append(f"{observation_id}: unsupported capability {capability!r}")
        confidence = observation.get("confidence")
        if confidence not in CONFIDENCE_LEVELS:
            errors.append(f"{observation_id}: unsupported confidence {confidence!r}")
        evidence_ids = observation.get("evidenceIds", [])
        if not evidence_ids:
            errors.append(f"{observation_id}: observation must cite at least one evidence source")
        for evidence_id in evidence_ids:
            source = sources.get(evidence_id)
            if not source:
                errors.append(f"{observation_id}: missing evidence source {evidence_id}")
                continue
            capabilities = set(source.get("evidenceCapabilities", []))
            if capability not in capabilities:
                errors.append(
                    f"{observation_id}: source {evidence_id} is not declared capable of supporting {capability}"
                )

    for group_name, evidence_ids in (profile.get("evidenceGroups") or {}).items():
        for evidence_id in evidence_ids:
            if evidence_id not in sources:
                errors.append(f"evidence group {group_name} references unknown source {evidence_id}")

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "sourceCount": len(source_rows),
        "observationCount": len(profile.get("observations", [])),
        "targetEpoch": profile.get("targetEpoch"),
    }


def require_reference_profile_v02(profile: dict[str, Any]) -> dict[str, Any]:
    report = validate_reference_profile_v02(profile)
    if report["status"] != "pass":
        raise EvidenceError("reference profile integrity failure: " + "; ".join(report["errors"]))
    return report


def production_orientation_gate(spec: dict[str, Any]) -> dict[str, Any]:
    orientation = spec.get("orientation") or {}
    policy = orientation.get("policy", "unknown")
    review_status = orientation.get("reviewStatus", "unreviewed")
    production_tier = spec.get("productionTier")
    stage = spec.get("productionStage", "prototype")
    blocked = False
    reasons: list[str] = []

    if production_tier == "hero-exterior" and stage in {"visual-review", "production-ready"}:
        if policy in {"unknown", "longest-edge-proxy"}:
            blocked = True
            reasons.append("hero visual-review/production assets require a reviewed facade orientation policy")
        if review_status != "reviewed":
            blocked = True
            reasons.append("hero visual-review/production assets require reviewStatus=reviewed")
        if not orientation.get("evidenceIds"):
            blocked = True
            reasons.append("reviewed facade orientation must cite evidence")

    return {
        "status": "fail" if blocked else "pass",
        "policy": policy,
        "reviewStatus": review_status,
        "reasons": reasons,
    }
