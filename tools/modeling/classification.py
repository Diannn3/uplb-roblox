from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import BuildingRecord, SourceLead


@dataclass(frozen=True)
class Classification:
    strategy: str
    confidence: str
    score: int
    reasons: tuple[str, ...]


def classify_building(building: BuildingRecord, sources: Iterable[SourceLead]) -> Classification:
    """Recommend a production strategy without silently overriding human registry choices.

    Scoring intentionally favors recoverable original models and explicitly reusable scans,
    then capture/custom work for important buildings, then procedural production.
    """

    source_list = tuple(sources)
    score = 0
    reasons: list[str] = []
    kinds = {source.kind for source in source_list}
    reusable = {source.reuse_status for source in source_list}

    if "legacy-project-evidence" in kinds:
        score += 35
        reasons.append("legacy UPLB 3D project evidence exists")
    if "existing-3d-scan-lead" in kinds:
        score += 30
        reasons.append("existing high-density scan lead exists")
    if any(status.startswith("CC-") or "permission-granted" in status for status in reusable):
        score += 20
        reasons.append("at least one source is explicitly reusable")
    if "licensed-photography" in kinds:
        score += 10
        reasons.append("licensed photographic reference exists")
    if "institutional-building-study" in kinds:
        score += 8
        reasons.append("institutional building study provides factual constraints")
    if building.priority == "A":
        score += 20
        reasons.append("priority A visual landmark")
    elif building.priority == "B":
        score += 8
        reasons.append("priority B campus building")

    if "existing-3d-scan-lead" in kinds:
        strategy = "existing-scan-with-permission"
    elif "legacy-project-evidence" in kinds:
        strategy = "recover-existing"
    elif building.priority == "A":
        strategy = "custom-hero"
    elif building.known_facts:
        strategy = "procedural-accurate"
    else:
        strategy = "procedural-context"

    confidence = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return Classification(strategy=strategy, confidence=confidence, score=score, reasons=tuple(reasons))
