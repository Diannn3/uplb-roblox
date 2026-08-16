"""Overture candidate adapter.

The adapter is deliberately read-only: it parses a fetched GeoJSON extract when
one is available, but it never treats provider data as canonical without review.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from .io import read_json, sha256
from .models import CanonicalFeature, SourceRecord


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "unnamed"


def _name(properties: dict[str, Any], identifier: str) -> str:
    names = properties.get("names")
    if isinstance(names, dict):
        for value in names.values():
            if isinstance(value, dict) and value.get("value"):
                return str(value["value"])
            if isinstance(value, str):
                return value
    for key in ("name", "official_name"):
        if properties.get(key):
            return str(properties[key])
    return f"Overture building {identifier}"


def ingest_overture(path: Path, accessed_at: str = "2026-08-17") -> tuple[tuple[CanonicalFeature, ...], SourceRecord]:
    payload = read_json(path)
    features: list[CanonicalFeature] = []
    for index, item in enumerate(payload.get("features", [])):
        properties = item.get("properties") or {}
        external_id = str(properties.get("id") or item.get("id") or index)
        name = _name(properties, external_id)
        feature_id = f"uplb:building:overture-{_slug(external_id)}"
        features.append(
            CanonicalFeature(
                id=feature_id,
                feature_type="building",
                name=name,
                geometry=item.get("geometry"),
                aliases=(),
                properties={
                    "heightM": properties.get("height"),
                    "levels": properties.get("num_floors"),
                    "overtureProperties": properties,
                },
                external_ids={"overture": external_id},
                provenance=(f"source:overture:buildings@{accessed_at}",),
                confidence={"position": "medium", "footprint": "medium", "height": "medium", "facade": "unknown"},
                verification_status="needs-conflation-review",
            )
        )
    source = SourceRecord(
        id=f"source:overture:buildings@{accessed_at}",
        provider="Overture Maps Foundation",
        source_url="https://docs.overturemaps.org/guides/buildings/",
        accessed_at=accessed_at,
        license="ODbL-1.0",
        attribution="Overture Maps Foundation and upstream contributors",
        redistribution="allowed-with-conditions",
        rights_status="open-attribution-required",
        intended_use=("building-footprint", "building-height", "conflation-candidate"),
        content_hash=f"sha256:{sha256(path)}",
        notes=("Candidate source; never silently replaces a canonical feature.",),
    )
    return tuple(features), source
