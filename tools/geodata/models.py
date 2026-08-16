"""Canonical geodata contracts.

These dataclasses mirror the research JSON contracts while keeping the
implementation small enough to use from command-line tooling and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RightsStatus = Literal[
    "open-redistributable",
    "open-attribution-required",
    "share-alike",
    "internal-reference-only",
    "permission-required",
    "restricted-do-not-ingest",
    "uncertain",
    "blocked",
]


@dataclass(frozen=True)
class SourceRecord:
    """A traceable source and its rights state."""

    id: str
    provider: str
    source_url: str
    accessed_at: str
    rights_status: RightsStatus
    intended_use: tuple[str, ...]
    captured_at: str | None = None
    license: str | None = None
    attribution: str | None = None
    redistribution: str | None = None
    content_hash: str | None = None
    coverage: dict[str, Any] | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "provider": self.provider,
            "sourceUrl": self.source_url,
            "accessedAt": self.accessed_at,
            "rightsStatus": self.rights_status,
            "intendedUse": list(self.intended_use),
        }
        optional = {
            "capturedAt": self.captured_at,
            "license": self.license,
            "attribution": self.attribution,
            "redistribution": self.redistribution,
            "contentHash": self.content_hash,
            "coverage": self.coverage,
            "notes": list(self.notes),
        }
        result.update({key: value for key, value in optional.items() if value is not None})
        return result


@dataclass(frozen=True)
class CanonicalFeature:
    """A stable campus feature independent of any one upstream source."""

    id: str
    feature_type: str
    name: str
    geometry: dict[str, Any] | None
    provenance: tuple[str, ...]
    confidence: dict[str, str]
    verification_status: str
    aliases: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)
    external_ids: dict[str, str] = field(default_factory=dict)
    asset_binding: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "featureType": self.feature_type,
            "name": self.name,
            "aliases": list(self.aliases),
            "geometry": self.geometry,
            "properties": self.properties,
            "externalIds": self.external_ids,
            "provenance": list(self.provenance),
            "confidence": self.confidence,
            "verificationStatus": self.verification_status,
            "assetBinding": self.asset_binding,
        }

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "geometry": self.geometry,
            "properties": {
                "featureType": self.feature_type,
                "name": self.name,
                "aliases": list(self.aliases),
                "attributes": self.properties,
                "externalIds": self.external_ids,
                "provenance": list(self.provenance),
                "confidence": self.confidence,
                "verificationStatus": self.verification_status,
                "assetBinding": self.asset_binding,
            },
        }


@dataclass(frozen=True)
class ConflationReview:
    """Human-review record for candidates that cannot be safely auto-merged."""

    id: str
    canonical_id: str
    candidates: tuple[dict[str, Any], ...]
    decision: Literal["pending", "accept", "reject"] = "pending"
    reason: str = ""
    review_status: Literal["needs-review", "reviewed"] = "needs-review"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "canonicalId": self.canonical_id,
            "candidates": list(self.candidates),
            "decision": self.decision,
            "reason": self.reason,
            "reviewStatus": self.review_status,
        }


@dataclass
class ValidationReport:
    """Machine-readable gate result with no implicit pass-through."""

    id: str
    input_revisions: dict[str, Any]
    checks: list[dict[str, str]] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)
    discrepancies: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    decision: Literal["pass", "fail", "conditional"] = "conditional"

    def add_check(self, name: str, status: str, details: str = "") -> None:
        if status not in {"pass", "fail", "warning", "not-run"}:
            raise ValueError(f"unsupported check status: {status}")
        check = {"name": name, "status": status}
        if details:
            check["details"] = details
        self.checks.append(check)

    def finalize(self) -> None:
        statuses = {check["status"] for check in self.checks}
        if self.blockers or "fail" in statuses:
            self.decision = "fail"
        elif "warning" in statuses or "not-run" in statuses:
            self.decision = "conditional"
        else:
            self.decision = "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "inputRevisions": self.input_revisions,
            "checks": self.checks,
            "measurements": self.measurements,
            "discrepancies": self.discrepancies,
            "blockers": self.blockers,
            "decision": self.decision,
        }
