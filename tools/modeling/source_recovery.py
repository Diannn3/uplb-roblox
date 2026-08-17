from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .models import BuildingRecord, SourceLead


@dataclass(frozen=True)
class RecoveryAction:
    production_id: str
    building_name: str
    priority: str
    action: str
    source_id: str | None
    rationale: str


def build_recovery_queue(buildings: Iterable[BuildingRecord], sources: dict[str, SourceLead]) -> list[RecoveryAction]:
    queue: list[RecoveryAction] = []
    for building in buildings:
        source_rows = [sources[source_id] for source_id in building.source_ids if source_id in sources]
        legacy = next((row for row in source_rows if row.kind == "legacy-project-evidence"), None)
        scan = next((row for row in source_rows if row.kind == "existing-3d-scan-lead"), None)
        if scan:
            queue.append(RecoveryAction(building.id, building.name, building.priority, "request-scan-license-and-original", scan.id, "An existing high-density model may avoid duplicate capture/modeling."))
        if legacy:
            queue.append(RecoveryAction(building.id, building.name, building.priority, "request-2014-original-model", legacy.id, "The 2014 UPLB project may contain blueprint-patterned source geometry."))
        if not scan and not legacy and building.priority in {"A", "B"}:
            queue.append(RecoveryAction(building.id, building.name, building.priority, "build-reference-pack", None, "No recoverable 3D source is registered yet."))
    priority_order={"A":0,"B":1,"C":2,"D":3}
    action_order={"request-scan-license-and-original":0,"request-2014-original-model":1,"build-reference-pack":2}
    queue.sort(key=lambda row:(priority_order[row.priority],action_order[row.action],row.building_name))
    return queue


def recovery_queue_dict(queue: Iterable[RecoveryAction]) -> list[dict[str, object]]:
    return [asdict(row) for row in queue]
