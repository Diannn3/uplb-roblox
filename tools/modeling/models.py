from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Priority = Literal["A", "B", "C", "D"]
ModelStrategy = Literal[
    "recover-existing",
    "existing-scan-with-permission",
    "photogrammetry",
    "custom-hero",
    "procedural-accurate",
    "procedural-context",
    "environment-system",
    "background-only",
]


@dataclass(frozen=True)
class SourceLead:
    id: str
    title: str
    kind: str
    rights_status: str
    reuse_status: str
    url: str


@dataclass(frozen=True)
class BuildingRecord:
    id: str
    name: str
    priority: Priority
    production_tier: str
    primary_strategy: ModelStrategy
    fallback_strategy: str
    source_ids: tuple[str, ...]
    status: str
    canonical_feature_id: str | None = None
    proposed_feature_id: str | None = None
    architectural_family: str | None = None
    known_facts: dict[str, Any] | None = None

    @property
    def feature_id(self) -> str:
        value = self.canonical_feature_id or self.proposed_feature_id
        if not value:
            raise ValueError(f"{self.id} has no feature identifier")
        return value
