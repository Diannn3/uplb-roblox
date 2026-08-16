"""Lightweight validation of the production schema bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .io import read_json


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "data" / "canonical" / "schemas"

EXPECTED: dict[str, tuple[str, ...]] = {
    "source-record.schema.json": ("id", "provider", "sourceUrl", "accessedAt", "rightsStatus", "status", "intendedUse"),
    "canonical-feature.schema.json": ("id", "featureType", "name", "provenance", "confidence", "verificationStatus"),
    "building-spec.schema.json": ("featureId", "referenceIds", "productionTier", "verificationStatus"),
    "asset-manifest.schema.json": ("assetId", "featureIds", "sourceSpecHash", "productionMethod", "rightsRecords", "verificationStatus"),
    "ai-building-handoff.schema.json": ("featureId", "buildingSpec", "referenceIndex", "openQuestions", "allowedActions"),
    "validation-report.schema.json": ("id", "inputRevisions", "checks", "decision"),
    "conflation-review.schema.json": ("id", "canonicalId", "candidateIds", "metrics", "recommendation", "decision", "reviewStatus"),
    "identity-registry.schema.json": ("version", "nextNumbers", "deletedIds", "entities"),
}


def validate_schema_documents(schema_dir: Path = SCHEMA_DIR) -> list[str]:
    errors: list[str] = []
    for filename, required in EXPECTED.items():
        path = schema_dir / filename
        if not path.exists():
            errors.append(f"missing schema: {filename}")
            continue
        try:
            payload: dict[str, Any] = read_json(path)
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(f"invalid JSON {filename}: {exc}")
            continue
        if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{filename}: wrong $schema")
        missing = [key for key in required if key not in payload.get("required", [])]
        if missing:
            errors.append(f"{filename}: missing required declarations {missing}")
    return errors


def _validate_instance(instance: Any, schema_path: Path, label: str) -> list[str]:
    schema = read_json(schema_path)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"{label} {location}: {error.message}")
    return errors


def validate_artifacts(root: Path = ROOT) -> list[str]:
    """Validate tracked canonical artifacts against the production schemas."""

    errors = validate_schema_documents(root / "data" / "canonical" / "schemas")
    artifact_root = root / "data" / "canonical"
    schema_root = artifact_root / "schemas"
    canonical_path = artifact_root / "features.geojson"
    if canonical_path.exists():
        payload = read_json(canonical_path)
        for index, feature in enumerate(payload.get("features", [])):
            properties = feature.get("properties") or {}
            flat = {
                "id": feature.get("id"),
                "featureType": properties.get("featureType"),
                "name": properties.get("name"),
                "aliases": properties.get("aliases", []),
                "geometry": feature.get("geometry"),
                "properties": properties.get("attributes", {}),
                "externalIds": properties.get("externalIds", {}),
                "provenance": properties.get("provenance", []),
                "confidence": properties.get("confidence", {}),
                "verificationStatus": properties.get("verificationStatus"),
                "assetBinding": properties.get("assetBinding"),
            }
            errors.extend(_validate_instance(flat, schema_root / "canonical-feature.schema.json", f"canonical feature {index}"))
    source_path = artifact_root / "source-records.json"
    if source_path.exists():
        for index, source in enumerate(read_json(source_path).get("sources", [])):
            errors.extend(_validate_instance(source, schema_root / "source-record.schema.json", f"source record {index}"))
    registry_path = artifact_root / "identity-registry.json"
    if registry_path.exists():
        errors.extend(_validate_instance(read_json(registry_path), schema_root / "identity-registry.schema.json", "identity registry"))
    validation_path = artifact_root / "validation-report.json"
    if validation_path.exists():
        errors.extend(_validate_instance(read_json(validation_path), schema_root / "validation-report.schema.json", "validation report"))
    review_path = artifact_root / "review-decisions.json"
    if review_path.exists():
        for index, review in enumerate(read_json(review_path).get("decisions", [])):
            errors.extend(_validate_instance(review, schema_root / "conflation-review.schema.json", f"review {index}"))
    return errors


def main() -> int:
    errors = validate_schema_documents()
    if not errors:
        errors.extend(validate_artifacts())
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: validated {len(EXPECTED)} production schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
