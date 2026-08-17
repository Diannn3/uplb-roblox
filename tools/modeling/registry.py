from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .models import BuildingRecord, SourceLead

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = ROOT / "data" / "modeling" / "model-source-registry.json"
DEFAULT_BUILDINGS = ROOT / "data" / "modeling" / "building-production-registry.json"
DEFAULT_KIT = ROOT / "data" / "modeling" / "architecture-kit-v0.1.json"
SCHEMA_DIR = ROOT / "data" / "canonical" / "schemas"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = _read(SCHEMA_DIR / schema_name)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda item: list(item.absolute_path))
    if errors:
        rendered = "; ".join(f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors)
        raise ValueError(f"{schema_name} validation failed: {rendered}")


@dataclass(frozen=True)
class ModelingRegistry:
    source_document: dict[str, Any]
    building_document: dict[str, Any]
    kit_document: dict[str, Any]

    @property
    def sources(self) -> dict[str, SourceLead]:
        return {
            row["id"]: SourceLead(
                id=row["id"],
                title=row["title"],
                kind=row["kind"],
                rights_status=row["rightsStatus"],
                reuse_status=row["reuseStatus"],
                url=row["url"],
            )
            for row in self.source_document["sources"]
        }

    @property
    def buildings(self) -> tuple[BuildingRecord, ...]:
        return tuple(
            BuildingRecord(
                id=row["id"],
                name=row["name"],
                priority=row["priority"],
                production_tier=row["productionTier"],
                primary_strategy=row["primaryStrategy"],
                fallback_strategy=row["fallbackStrategy"],
                source_ids=tuple(row.get("sourceIds", [])),
                status=row["status"],
                canonical_feature_id=row.get("canonicalFeatureId"),
                proposed_feature_id=row.get("proposedFeatureId"),
                architectural_family=row.get("architecturalFamily"),
                known_facts=row.get("knownFacts"),
            )
            for row in self.building_document["buildings"]
        )

    def validate_cross_references(self) -> list[str]:
        errors: list[str] = []
        source_ids = set(self.sources)
        seen_production: set[str] = set()
        seen_features: set[str] = set()
        family_ids = {row["id"] for row in self.kit_document["families"]}
        component_ids = {row["id"] for row in self.kit_document["components"]}
        material_ids = {row["id"] for row in self.kit_document["materialClasses"]}

        if len(component_ids) != len(self.kit_document["components"]):
            errors.append("architecture kit has duplicate component IDs")
        if len(family_ids) != len(self.kit_document["families"]):
            errors.append("architecture kit has duplicate family IDs")
        if len(material_ids) != len(self.kit_document["materialClasses"]):
            errors.append("architecture kit has duplicate material IDs")

        for component in self.kit_document["components"]:
            if component["materialClass"] not in material_ids:
                errors.append(f"{component['id']} references unknown material {component['materialClass']}")

        for building in self.buildings:
            if building.id in seen_production:
                errors.append(f"duplicate production record {building.id}")
            seen_production.add(building.id)
            if building.feature_id in seen_features:
                errors.append(f"duplicate feature binding {building.feature_id}")
            seen_features.add(building.feature_id)
            for source_id in building.source_ids:
                if source_id not in source_ids:
                    errors.append(f"{building.id} references missing source {source_id}")
            if building.architectural_family and building.architectural_family not in family_ids:
                errors.append(f"{building.id} references unknown architecture family {building.architectural_family}")
        return errors

    def summary(self) -> dict[str, Any]:
        strategy_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        canonical_bound = 0
        for building in self.buildings:
            strategy_counts[building.primary_strategy] = strategy_counts.get(building.primary_strategy, 0) + 1
            priority_counts[building.priority] = priority_counts.get(building.priority, 0) + 1
            status_counts[building.status] = status_counts.get(building.status, 0) + 1
            canonical_bound += int(building.canonical_feature_id is not None)
        return {
            "sourceCount": len(self.sources),
            "buildingCount": len(self.buildings),
            "canonicalBoundCount": canonical_bound,
            "proposedBindingCount": len(self.buildings) - canonical_bound,
            "architectureFamilyCount": len(self.kit_document["families"]),
            "componentCount": len(self.kit_document["components"]),
            "materialClassCount": len(self.kit_document["materialClasses"]),
            "strategyCounts": dict(sorted(strategy_counts.items())),
            "priorityCounts": dict(sorted(priority_counts.items())),
            "statusCounts": dict(sorted(status_counts.items())),
        }


def load_registry(
    sources_path: Path = DEFAULT_SOURCES,
    buildings_path: Path = DEFAULT_BUILDINGS,
    kit_path: Path = DEFAULT_KIT,
) -> ModelingRegistry:
    sources = _read(sources_path)
    buildings = _read(buildings_path)
    kit = _read(kit_path)
    _validate(sources, "model-source-registry.schema.json")
    _validate(buildings, "building-production-registry.schema.json")
    _validate(kit, "architecture-kit.schema.json")
    registry = ModelingRegistry(sources, buildings, kit)
    errors = registry.validate_cross_references()
    if errors:
        raise ValueError("modeling registry cross-reference failure: " + "; ".join(errors))
    return registry
