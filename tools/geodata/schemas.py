"""Lightweight validation of the production schema bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "data" / "canonical" / "schemas"

EXPECTED: dict[str, tuple[str, ...]] = {
    "source-record.schema.json": ("id", "provider", "sourceUrl", "accessedAt", "rightsStatus", "intendedUse"),
    "canonical-feature.schema.json": ("id", "featureType", "name", "provenance", "confidence", "verificationStatus"),
    "building-spec.schema.json": ("featureId", "referenceIds", "productionTier", "verificationStatus"),
    "asset-manifest.schema.json": ("assetId", "featureIds", "sourceSpecHash", "productionMethod", "rightsRecords", "verificationStatus"),
    "ai-building-handoff.schema.json": ("featureId", "buildingSpec", "referenceIndex", "openQuestions", "allowedActions"),
    "validation-report.schema.json": ("id", "inputRevisions", "checks", "decision"),
    "conflation-review.schema.json": ("id", "canonicalId", "candidates", "decision", "reviewStatus"),
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


def main() -> int:
    errors = validate_schema_documents()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: validated {len(EXPECTED)} production schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
