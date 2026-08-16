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


VerificationStatus = Literal[
    "unknown",
    "provisional",
    "source-supported",
    "human-reviewed",
    "verified",
    "conflicting",
]


VerificationMap = dict[str, str]


@dataclass(frozen=True)
class SourceRecord:
    """A traceable source and its rights state."""

    id: str
    provider: str
    source_url: str
    accessed_at: str
    rights_status: RightsStatus
    intended_use: tuple[str, ...]
    status: str = "validated"
    captured_at: str | None = None
    license: str | None = None
    attribution: str | None = None
    redistribution: str | None = None
    content_hash: str | None = None
    coverage: dict[str, Any] | None = None
    notes: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "provider": self.provider,
            "sourceUrl": self.source_url,
            "accessedAt": self.accessed_at,
            "rightsStatus": self.rights_status,
            "status": self.status,
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
            "metadata": self.metadata,
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
    verification: VerificationMap = field(default_factory=dict)

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
            "verification": self.verification,
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
                "verification": self.verification,
            },
        }


@dataclass(frozen=True)
class ProviderCandidate:
    """A normalized provider record that has not been promoted to campus truth."""

    id: str
    provider: str
    feature_type: str
    name: str
    geometry: dict[str, Any] | None
    provenance: tuple[str, ...]
    external_ids: dict[str, str]
    confidence: dict[str, str]
    properties: dict[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    verification_status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "featureType": self.feature_type,
            "name": self.name,
            "aliases": list(self.aliases),
            "geometry": self.geometry,
            "properties": self.properties,
            "externalIds": self.external_ids,
            "provenance": list(self.provenance),
            "confidence": self.confidence,
            "verificationStatus": self.verification_status,
        }

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "geometry": self.geometry,
            "properties": {
                "provider": self.provider,
                "featureType": self.feature_type,
                "name": self.name,
                "aliases": list(self.aliases),
                "attributes": self.properties,
                "externalIds": self.external_ids,
                "provenance": list(self.provenance),
                "confidence": self.confidence,
                "verificationStatus": self.verification_status,
            },
        }


@dataclass(frozen=True)
class ConflationReview:
    """Human-review record for candidates that cannot be safely auto-merged."""

    id: str
    canonical_id: str | None
    candidate_ids: dict[str, str]
    metrics: dict[str, float]
    recommendation: Literal["probable-match", "possible-match", "no-match"]
    decision: Literal["pending", "accept", "reject"] = "pending"
    reason: str = ""
    review_status: Literal["needs-review", "reviewed"] = "needs-review"

    @property
    def candidates(self) -> tuple[dict[str, Any], ...]:
        return tuple({"provider": key, "candidateId": value} for key, value in sorted(self.candidate_ids.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "canonicalId": self.canonical_id,
            "candidateIds": self.candidate_ids,
            "metrics": self.metrics,
            "recommendation": self.recommendation,
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
    engineering_gate: Literal["pass", "fail"] = "fail"
    canonical_identity_gate: Literal["pass", "fail"] = "fail"
    geometry_gate: Literal["pass", "fail"] = "fail"
    reproducibility_gate: Literal["pass", "fail"] = "fail"
    human_review_gate: Literal["pending", "pass"] = "pending"
    dem_rights_gate: Literal["pending", "pass", "fail"] = "pending"
    overture_comparison_gate: Literal["pass", "deferred", "blocked"] = "deferred"
    worldgen_ready: bool = False
    campus_wide_production_ready: bool = False

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
            "engineeringGate": self.engineering_gate,
            "canonicalIdentityGate": self.canonical_identity_gate,
            "geometryGate": self.geometry_gate,
            "reproducibilityGate": self.reproducibility_gate,
            "humanReviewGate": self.human_review_gate,
            "demRightsGate": self.dem_rights_gate,
            "overtureComparisonGate": self.overture_comparison_gate,
            "worldgenReady": self.worldgen_ready,
            "campusWideProductionReady": self.campus_wide_production_ready,
        }
