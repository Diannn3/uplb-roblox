from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .asset_manifest import write_prototype_asset_manifest
from .budgets import budget_for
from .baker_hall import generate_baker_hall_outputs
from .classification import classify_building
from .prototypes import generate_baker_massing, generate_kit_prototypes
from .reference_building import SPEC_DIR as CENTRAL_SPEC_DIR, generate_central_wave_outputs
from .registry import ROOT, load_registry
from .source_recovery import build_recovery_queue, recovery_queue_dict

REPORT_PATH = ROOT / "data" / "modeling" / "production-foundation-report.json"
RECOVERY_PATH = ROOT / "data" / "modeling" / "source-recovery-queue.json"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_baker_specs() -> None:
    schema = json.loads((ROOT / "data" / "canonical" / "schemas" / "building-spec-v0.2.schema.json").read_text(encoding="utf-8"))
    for name in ("baker-hall.v0.1.json", "baker-hall.v0.2.json"):
        spec = json.loads((ROOT / "data" / "modeling" / "building-specs" / name).read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(spec))
        if errors:
            raise ValueError(f"{name} schema failure: " + "; ".join(error.message for error in errors))

    reference_schema = json.loads((ROOT / "data" / "canonical" / "schemas" / "building-reference-profile.schema.json").read_text(encoding="utf-8"))
    reference = json.loads((ROOT / "data" / "modeling" / "reference" / "baker-hall.reference-profile.json").read_text(encoding="utf-8"))
    reference_errors = list(Draft202012Validator(reference_schema).iter_errors(reference))
    if reference_errors:
        raise ValueError("Baker reference profile schema failure: " + "; ".join(error.message for error in reference_errors))


def _validate_central_wave_specs() -> None:
    schema = json.loads((ROOT / "data" / "canonical" / "schemas" / "reference-building-production-spec.schema.json").read_text(encoding="utf-8"))
    reference_schema = json.loads((ROOT / "data" / "canonical" / "schemas" / "building-reference-profile.schema.json").read_text(encoding="utf-8"))
    for spec_path in sorted(CENTRAL_SPEC_DIR.glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(spec))
        if errors:
            raise ValueError(f"{spec_path.name} schema failure: " + "; ".join(error.message for error in errors))
        feature_path = ROOT / spec["featureSnapshot"]
        feature = json.loads(feature_path.read_text(encoding="utf-8"))
        if feature.get("id") != spec["sourceFeatureId"]:
            raise ValueError(f"{spec_path.name}: feature snapshot id mismatch")
        reference_path = ROOT / spec.get("referenceProfile", "")
        if reference_path.is_file():
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            ref_errors = list(Draft202012Validator(reference_schema).iter_errors(reference))
            if ref_errors:
                raise ValueError(f"{reference_path.name} schema failure: " + "; ".join(error.message for error in ref_errors))
            if reference.get("featureId") != spec["proposedFeatureId"]:
                raise ValueError(f"{spec_path.name}: reference profile id mismatch")


def build_report(*, generate_prototypes: bool, generate_baker_production: bool = False, generate_central_wave: bool = False) -> dict[str, Any]:
    registry = load_registry()
    _validate_baker_specs()
    _validate_central_wave_specs()
    sources = registry.sources
    classification=[]
    for building in registry.buildings:
        result=classify_building(building,(sources[source_id] for source_id in building.source_ids))
        classification.append({
            "productionId":building.id,
            "featureId":building.feature_id,
            "name":building.name,
            "registeredStrategy":building.primary_strategy,
            "recommendedStrategy":result.strategy,
            "confidence":result.confidence,
            "score":result.score,
            "reasons":list(result.reasons),
            "budget":budget_for(building.production_tier).to_dict(),
        })
    queue=build_recovery_queue(registry.buildings,sources)
    RECOVERY_PATH.parent.mkdir(parents=True,exist_ok=True)
    RECOVERY_PATH.write_text(json.dumps({"schemaVersion":"uplb-source-recovery-queue-v0.1","actions":recovery_queue_dict(queue)},indent=2)+"\n",encoding="utf-8")
    prototype_result=None
    kit_prototypes=[]
    asset_manifest = None
    baker_production = None
    central_wave = []
    if generate_prototypes:
        prototype_result=generate_baker_massing()
        kit_prototypes=generate_kit_prototypes()
        asset_manifest = write_prototype_asset_manifest()
        prototype_schema = json.loads((ROOT / "data" / "canonical" / "schemas" / "modeling-prototype-assets.schema.json").read_text(encoding="utf-8"))
        prototype_errors = list(Draft202012Validator(prototype_schema).iter_errors(asset_manifest))
        if prototype_errors:
            raise ValueError("prototype asset manifest schema failure: " + "; ".join(error.message for error in prototype_errors))
    if generate_baker_production:
        baker_production = generate_baker_hall_outputs()
    if generate_central_wave:
        central_wave = generate_central_wave_outputs()
    report={
        "schemaVersion":"uplb-modeling-production-foundation-v0.1",
        "status":"pass",
        "summary":registry.summary(),
        "classification":classification,
        "recoveryActionCount":len(queue),
        "topRecoveryActions":recovery_queue_dict(queue[:12]),
        "prototype":prototype_result,
        "kitPrototypeCount":len(kit_prototypes),
        "prototypeAssetCount": len(asset_manifest["records"]) if asset_manifest else 0,
        "bakerProduction": baker_production,
        "centralWaveProductionCount": len(central_wave),
        "centralWaveProduction": central_wave,
        "inputs":{
            "modelSourceRegistry":{"path":"data/modeling/model-source-registry.json","sha256":_sha256(ROOT/"data/modeling/model-source-registry.json")},
            "buildingProductionRegistry":{"path":"data/modeling/building-production-registry.json","sha256":_sha256(ROOT/"data/modeling/building-production-registry.json")},
            "architectureKit":{"path":"data/modeling/architecture-kit-v0.1.json","sha256":_sha256(ROOT/"data/modeling/architecture-kit-v0.1.json")},
            "bakerPrototypeSpec":{"path":"data/modeling/building-specs/baker-hall.v0.1.json","sha256":_sha256(ROOT/"data/modeling/building-specs/baker-hall.v0.1.json")},
            "bakerProductionSpec":{"path":"data/modeling/building-specs/baker-hall.v0.2.json","sha256":_sha256(ROOT/"data/modeling/building-specs/baker-hall.v0.2.json")},
            "bakerReferenceProfile":{"path":"data/modeling/reference/baker-hall.reference-profile.json","sha256":_sha256(ROOT/"data/modeling/reference/baker-hall.reference-profile.json")}
        },
        "nextGate":"Visually review Baker Hall v0.2 first, then review the central-wave evidence-aware prototypes. Replace all provisional facade orientation/dimensions with stronger recovered/model/measurement evidence before final architectural approval.",
    }
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description="Validate the UPLB campus modeling production foundation.")
    parser.add_argument("--check",action="store_true",help="Validate registries and deterministic policies.")
    parser.add_argument("--generate-prototypes",action="store_true",help="Generate Baker massing and architecture-kit primitive prototypes.")
    parser.add_argument("--generate-baker-production",action="store_true",help="Generate the reference-derived Baker Hall v0.2 exterior OBJ and report.")
    parser.add_argument("--generate-central-wave",action="store_true",help="Generate evidence-aware central-campus building prototypes from source feature snapshots.")
    parser.add_argument("--write-report",action="store_true",help="Write production-foundation-report.json.")
    args=parser.parse_args()
    report=build_report(generate_prototypes=args.generate_prototypes, generate_baker_production=args.generate_baker_production, generate_central_wave=args.generate_central_wave)
    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True,exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
