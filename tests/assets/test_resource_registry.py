"""Contract tests for the external asset/tooling gap registry."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[2]
REGISTRY_PATH = ROOT / "assets" / "manifests" / "resource-registry.json"
SCHEMA_PATH = ROOT / "assets" / "manifests" / "resource-registry.schema.json"
INGEST_PATH = ROOT / "research" / "asset-ingest" / "INGEST_RECORD.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_resource_registry_matches_schema() -> None:
    schema = _read_json(SCHEMA_PATH)
    registry = _read_json(REGISTRY_PATH)
    errors = sorted(Draft202012Validator(schema).iter_errors(registry), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def test_resource_ids_are_unique_and_urls_are_reviewable() -> None:
    registry = _read_json(REGISTRY_PATH)
    resources = registry["resources"]
    ids = [resource["id"] for resource in resources]
    assert len(ids) == len(set(ids))
    assert all(resource["sourceUrl"].startswith(("https://", "http://")) for resource in resources)
    assert all(resource["disposition"] != "ADOPT_NOW" for resource in resources)


def test_registry_records_user_bundle_without_binaries() -> None:
    registry = _read_json(REGISTRY_PATH)
    ingest = _read_json(INGEST_PATH)
    bundle = registry["sourceBundle"]
    assert bundle["binaryAssetsIncluded"] is False
    assert len(bundle["zipSha256"]) == 64
    assert len(bundle["registrySha256"]) == 64
    assert ingest["extractionComplete"] is True
    assert ingest["zipEntryCount"] == 26
    assert ingest["resourceCount"] == 15
    assert ingest["binaryAssetCount"] == 0
    assert ingest["zipSha256"] == bundle["zipSha256"]
    assert ingest["registrySha256"] == bundle["registrySha256"]
