from __future__ import annotations

from typing import Any


def object_metadata(properties: dict[str, Any], *, input_hash: str, terrain_revision: str, generator_version: str) -> dict[str, Any]:
    verification = properties.get("verification") or {}
    return {
        "FeatureId": properties.get("featureId"),
        "CandidateId": properties.get("candidateId"),
        "SourceLifecycle": properties.get("sourceLifecycle"),
        "WorldgenRole": properties.get("worldgenRole"),
        "DetailTier": properties.get("detailTier"),
        "VerificationStatus": properties.get("verificationStatus"),
        "GeometryConfidence": properties.get("geometryConfidence", verification.get("footprint", "unknown")),
        "HeightConfidence": verification.get("height", "unknown"),
        "CanonicalRevision": properties.get("canonicalRevision"),
        "TerrainRevision": terrain_revision,
        "GeneratorVersion": generator_version,
        "InputHash": input_hash,
    }
