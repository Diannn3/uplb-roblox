"""Persistent campus-domain identity registry and promotion helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .io import read_json, write_json
from .models import CanonicalFeature, ProviderCandidate


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def semantic_slug(feature_type: str, name: str) -> str | None:
    normalized = normalize_name(name)
    if "baker hall" in normalized or "baker memorial" in normalized:
        return "building:baker-hall"
    if normalized == "oblation" or "uplb oblation" in normalized:
        return "landmark:oblation"
    if "freedom park" in normalized:
        return "landmark:freedom-park"
    return None


@dataclass
class IdentityRegistry:
    version: int = 1
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    next_numbers: dict[str, int] = field(default_factory=lambda: {"building": 1, "road": 1, "walkway": 1, "landmark": 1})
    deleted_ids: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "IdentityRegistry":
        payload = read_json(path)
        return cls(
            version=int(payload.get("version", 1)),
            entities=dict(payload.get("entities", {})),
            next_numbers={key: int(value) for key, value in payload.get("nextNumbers", {}).items()},
            deleted_ids=list(payload.get("deletedIds", [])),
        )

    @classmethod
    def empty(cls) -> "IdentityRegistry":
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "nextNumbers": dict(sorted(self.next_numbers.items())),
            "deletedIds": sorted(set(self.deleted_ids)),
            "entities": {key: self.entities[key] for key in sorted(self.entities)},
        }

    def save(self, path: Path) -> None:
        write_json(path, self.to_dict())

    def _find_by_name_or_external(self, name: str, external_ids: dict[str, str]) -> str | None:
        normalized = normalize_name(name)
        for canonical_id, entity in self.entities.items():
            names = [entity.get("canonicalName", ""), *entity.get("aliases", [])]
            if normalized and normalized in {normalize_name(candidate) for candidate in names}:
                return canonical_id
            for provider, external_id in external_ids.items():
                if external_id in entity.get("externalIds", {}).get(provider, []):
                    return canonical_id
        return None

    def _allocate_opaque(self, feature_type: str) -> str:
        prefixes = {"building": "bldg", "road": "road", "walkway": "path", "landmark": "landmark"}
        prefix = prefixes.get(feature_type, feature_type)
        number = self.next_numbers.get(feature_type, 1)
        while True:
            candidate = f"uplb:{feature_type}:{prefix}-{number:06d}"
            number += 1
            if candidate not in self.entities and candidate not in self.deleted_ids:
                self.next_numbers[feature_type] = number
                return candidate

    def resolve_or_allocate(
        self,
        feature_type: str,
        name: str,
        external_ids: dict[str, str],
        *,
        promote: bool,
    ) -> str | None:
        existing = self._find_by_name_or_external(name, external_ids)
        if existing:
            return existing
        if not promote:
            return None
        canonical_id = semantic_slug(feature_type, name) or self._allocate_opaque(feature_type)
        self.entities[canonical_id] = {
            "featureType": feature_type,
            "canonicalName": name,
            "aliases": [],
            "externalIds": {provider: [value] for provider, value in external_ids.items()},
            "identityStatus": "needs-review",
            "createdFrom": "explicit-promotion",
            "supersedes": [],
        }
        return canonical_id

    def update_external_id(self, canonical_id: str, provider: str, external_id: str) -> None:
        if canonical_id not in self.entities:
            raise KeyError(f"unknown canonical ID: {canonical_id}")
        external_ids = self.entities[canonical_id].setdefault("externalIds", {})
        values = external_ids.setdefault(provider, [])
        if external_id not in values:
            values.append(external_id)
            values.sort()

    def reconcile_candidates(self, candidates: Iterable[ProviderCandidate]) -> None:
        """Record no deletions: missing upstream candidates never erase campus truth."""

        _ = list(candidates)

    def promote_candidate(self, candidate: ProviderCandidate, canonical_id: str | None = None) -> CanonicalFeature:
        canonical_id = canonical_id or self.resolve_or_allocate(
            candidate.feature_type,
            candidate.name,
            candidate.external_ids,
            promote=True,
        )
        assert canonical_id is not None
        entity = self.entities[canonical_id]
        entity["canonicalName"] = entity.get("canonicalName") or candidate.name
        entity["identityStatus"] = entity.get("identityStatus", "needs-review")
        for provider, external_id in candidate.external_ids.items():
            self.update_external_id(canonical_id, provider, external_id)
        return CanonicalFeature(
            id=canonical_id,
            feature_type=entity["featureType"],
            name=entity["canonicalName"],
            geometry=candidate.geometry,
            aliases=tuple(entity.get("aliases", [])),
            properties=candidate.properties,
            external_ids=candidate.external_ids,
            provenance=candidate.provenance,
            confidence=candidate.confidence,
            verification_status=entity.get("identityStatus", "needs-review"),
        )
