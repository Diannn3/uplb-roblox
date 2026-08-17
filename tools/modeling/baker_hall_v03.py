from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .assembly import AssemblyPart, BuildingAssembly, write_obj_assembly
from .budgets import budget_for
from .evidence import production_orientation_gate, require_reference_profile_v02, validate_schema
from .geometry_v2 import extrude_local_geometry, project_wgs84_geometry_to_local_meters
from .mesh import MeshData, gable_prism_mesh, merge_meshes, oriented_box_mesh, oriented_cylinder_mesh, write_obj
from .orientation import FacadeFrame, resolve_front_frame
from .qa import validate_assembly_geometry
from .registry import ROOT

SPEC_PATH = ROOT / "data" / "modeling" / "building-specs" / "baker-hall.v0.3.json"
REFERENCE_PATH = ROOT / "data" / "modeling" / "reference" / "baker-hall.reference-profile.v0.2.json"
SNAPSHOT_PATH = ROOT / "data" / "modeling" / "reference" / "baker-canonical-snapshot.geojson"
OUTPUT_DIR = ROOT / "assets" / "generated" / "production" / "baker-hall-v0.3"
LOGICAL_OUTPUT_DIR = "assets/generated/production/baker-hall-v0.3"
SPEC_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "reference-building-production-spec-v0.2.schema.json"
PROFILE_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "building-reference-profile-v0.2.schema.json"
MANIFEST_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "production-asset-manifest-v0.2.schema.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _feature(snapshot: dict[str, Any]) -> dict[str, Any]:
    return snapshot.get("feature") or snapshot


def _point(frame: FacadeFrame, along: float, outward: float, z: float) -> tuple[float, float, float]:
    return (
        frame.midpoint[0] + frame.tangent[0] * along + frame.outward[0] * outward,
        frame.midpoint[1] + frame.tangent[1] * along + frame.outward[1] * outward,
        z,
    )


def _box(
    frame: FacadeFrame,
    width: float,
    depth: float,
    height: float,
    *,
    along: float,
    outward: float,
    z: float,
) -> MeshData:
    return oriented_box_mesh(
        width,
        depth,
        height,
        center=_point(frame, along, outward, z),
        tangent_xy=frame.tangent,
        outward_xy=frame.outward,
    )


def _cylinder(
    frame: FacadeFrame,
    radius: float,
    height: float,
    *,
    along: float,
    outward: float,
    z: float,
    segments: int,
) -> MeshData:
    return oriented_cylinder_mesh(
        radius,
        height,
        center=_point(frame, along, outward, z),
        tangent_xy=frame.tangent,
        outward_xy=frame.outward,
        segments=segments,
    )


def _part(name: str, meshes: Iterable[MeshData], material: str, confidence: str, evidence: tuple[str, ...], notes: str) -> AssemblyPart:
    rows = tuple(meshes)
    if not rows:
        raise ValueError(f"{name}: empty mesh group")
    return AssemblyPart(name, merge_meshes(rows), material, confidence, evidence, notes)


def _front_modules(frame: FacadeFrame, spec: dict[str, Any], profile: dict[str, Any]) -> list[AssemblyPart]:
    dims = spec["referenceDerivedApproximation"]
    body_height = float(spec["height"]["meters"])
    floor_break = float(dims["groundFloorHeightM"])
    portico_width = min(float(dims["porticoWidthM"]), frame.length_m * 0.72)
    projection = float(dims["porticoProjectionM"])
    front_evidence = tuple(profile["evidenceGroups"]["frontFacade"])

    portico_meshes: list[MeshData] = [
        _box(frame, portico_width, projection, 0.28, along=0.0, outward=projection / 2.0, z=floor_break + 0.14)
    ]
    for along in (-6.0, -2.0, 2.0, 6.0):
        if abs(along) >= portico_width / 2.0 - 0.4:
            continue
        portico_meshes.append(_box(frame, 0.55, 0.55, floor_break, along=along, outward=projection - 0.35, z=floor_break / 2.0))
        upper_height = max(body_height - floor_break - 0.35, 1.0)
        portico_meshes.append(
            _cylinder(
                frame,
                0.32,
                upper_height,
                along=along,
                outward=projection - 0.35,
                z=floor_break + 0.28 + upper_height / 2.0,
                segments=12,
            )
        )
    portico_meshes.extend(
        [
            _box(frame, portico_width, 0.16, 0.16, along=0.0, outward=projection + 0.02, z=floor_break + 0.38),
            _box(frame, portico_width, 0.18, 0.18, along=0.0, outward=projection + 0.02, z=floor_break + 1.15),
            _box(frame, portico_width + 1.0, projection + 0.25, 0.42, along=0.0, outward=projection / 2.0, z=body_height - 0.25),
        ]
    )
    # Keep balusters deliberately modest in count; silhouette, not conservation survey.
    for index in range(14):
        along = -portico_width / 2.0 + 0.6 + index * (portico_width - 1.2) / 13.0
        portico_meshes.append(_box(frame, 0.13, 0.13, 0.72, along=along, outward=projection + 0.02, z=floor_break + 0.765))

    window_meshes: list[MeshData] = []
    awning_meshes: list[MeshData] = []
    bay_count = int(dims["wingBayCountEachSide"])
    usable_half = max(frame.length_m / 2.0 - portico_width / 2.0 - 1.5, 1.0)
    each_side_positions = [
        portico_width / 2.0 + 1.5 + usable_half * (index + 0.5) / bay_count
        for index in range(bay_count)
    ]
    bay_positions = tuple(-value for value in reversed(each_side_positions)) + tuple(each_side_positions)
    for window_z, awning_z in ((2.05, 3.12), (5.95, 7.05)):
        for along in bay_positions:
            window_meshes.append(_box(frame, 2.65, 0.10, 1.55, along=along, outward=0.06, z=window_z))
            awning_meshes.append(_box(frame, 3.0, 0.78, 0.12, along=along, outward=0.42, z=awning_z))

    band_meshes = [
        _box(frame, frame.length_m + 0.4, 0.28, 0.28, along=0.0, outward=0.14, z=floor_break),
        _box(frame, frame.length_m + 0.4, 0.28, 0.32, along=0.0, outward=0.14, z=body_height - 0.35),
    ]
    parapet_meshes = [
        _box(frame, portico_width + 0.5, 0.42, 1.35, along=0.0, outward=0.18, z=body_height + 0.62)
    ]

    return [
        _part("Baker__Portico", portico_meshes, "concrete-painted", "high-visual", front_evidence, "Reference-derived front portico silhouette; dimensions remain provisional."),
        _part("Baker__FrontWindows", window_meshes, "painted-metal-glass-dark", "medium-visual", front_evidence, "Opening panels are visual proxies, not measured frames."),
        _part("Baker__FrontAwnings", awning_meshes, "painted-metal-green", "high-visual", front_evidence, "Green awning rhythm is visually supported; exact projection is provisional."),
        _part("Baker__Bands", band_meshes, "concrete-painted", "high-visual", front_evidence, "Major horizontal facade bands only."),
        _part("Baker__Parapet", parapet_meshes, "concrete-painted", "high-visual", front_evidence, "Central raised sign/parapet mass; lettering omitted."),
    ]


def compile_baker_v03() -> tuple[dict[str, BuildingAssembly], dict[str, Any]]:
    spec = _read(SPEC_PATH)
    profile = _read(REFERENCE_PATH)
    snapshot = _read(SNAPSHOT_PATH)
    validate_schema(spec, SPEC_SCHEMA, SPEC_PATH.name)
    validate_schema(profile, PROFILE_SCHEMA, REFERENCE_PATH.name)
    evidence_report = require_reference_profile_v02(profile)
    orientation_gate = production_orientation_gate(spec)
    if orientation_gate["status"] != "pass":
        raise ValueError("Baker v0.3 orientation gate failed: " + "; ".join(orientation_gate["reasons"]))

    feature = _feature(snapshot)
    if feature.get("id") != spec["sourceFeatureId"]:
        raise ValueError("Baker v0.3 source feature does not match canonical snapshot")
    projected = project_wgs84_geometry_to_local_meters(feature["geometry"])
    if projected["type"] != "Polygon":
        raise ValueError("Baker v0.3 currently expects one Polygon footprint")
    outer = [(float(p[0]), float(p[1])) for p in projected["coordinatesLocalMeters"][0][:-1]]
    frame = resolve_front_frame(
        outer,
        spec["orientation"],
        allow_proxy=spec["productionStage"] == "prototype",
    )

    body_height = float(spec["height"]["meters"])
    canonical_evidence = tuple(profile["evidenceGroups"]["canonicalGeometry"])
    shell = AssemblyPart(
        "Baker__Shell_A",
        extrude_local_geometry(projected, height_m=body_height),
        "concrete-painted",
        "source-supported-footprint/provisional-height",
        canonical_evidence,
        "Canonical footprint preserved; local origin is projected footprint centroid.",
    )
    front_parts = _front_modules(frame, spec, profile)

    dims = spec["referenceDerivedApproximation"]
    roof_evidence = tuple(profile["evidenceGroups"]["roofEnvelope"])
    roof = AssemblyPart(
        "Baker__Roof",
        gable_prism_mesh(
            min(float(dims["centralRoofWidthM"]), max(frame.length_m * 0.78, 4.0)),
            float(dims["centralRoofDepthM"]),
            eave_z=body_height - 0.05,
            ridge_z=float(dims["ridgeHeightM"]),
            center_xy=frame.midpoint,
            tangent_xy=frame.tangent,
            outward_xy=frame.outward,
        ),
        "corrugated-metal-green",
        "medium-low-visual",
        roof_evidence,
        "Roof is a replaceable envelope for multi-angle visual QA; ridge/eave geometry is not survey-derived.",
    )

    collision = AssemblyPart(
        "Baker__Collision",
        extrude_local_geometry(projected, height_m=max(body_height * 0.92, 1.0)),
        "collision-proxy",
        "software-derived",
        canonical_evidence,
        "Simple footprint collision proxy; not a visible production mesh.",
    )

    lod0_parts = (shell, *front_parts, roof)
    lod1_parts = (shell, front_parts[0], front_parts[3], front_parts[4], roof)
    lod2_parts = (shell, roof)
    lod3_parts = (shell,)
    assemblies = {
        "lod0": BuildingAssembly(spec["proposedFeatureId"], "baker-v0.3-lod0", tuple(lod0_parts), source_feature_id=spec["sourceFeatureId"], identity_status=spec["identityStatus"]),
        "lod1": BuildingAssembly(spec["proposedFeatureId"], "baker-v0.3-lod1", tuple(lod1_parts), source_feature_id=spec["sourceFeatureId"], identity_status=spec["identityStatus"]),
        "lod2": BuildingAssembly(spec["proposedFeatureId"], "baker-v0.3-lod2", tuple(lod2_parts), source_feature_id=spec["sourceFeatureId"], identity_status=spec["identityStatus"]),
        "lod3": BuildingAssembly(spec["proposedFeatureId"], "baker-v0.3-lod3", tuple(lod3_parts), source_feature_id=spec["sourceFeatureId"], identity_status=spec["identityStatus"]),
        "collision": BuildingAssembly(spec["proposedFeatureId"], "baker-v0.3-collision", (collision,), source_feature_id=spec["sourceFeatureId"], identity_status=spec["identityStatus"]),
    }

    budget = budget_for(spec["productionTier"])
    qa = {
        lod: validate_assembly_geometry(
            assembly,
            triangle_budget={
                "lod0": budget.aggregate_lod0_triangles,
                "lod1": budget.aggregate_lod1_triangles,
                "lod2": budget.aggregate_lod2_triangles,
                "lod3": budget.aggregate_lod3_triangles,
                "collision": budget.aggregate_lod2_triangles,
            }[lod],
            per_meshpart_triangle_budget=budget.per_meshpart_triangles,
            max_meshparts=budget.max_meshparts,
        )
        for lod, assembly in assemblies.items()
    }
    status = "pass" if all(row["status"] == "pass" for row in qa.values()) else "fail"
    report = {
        "schemaVersion": "uplb-baker-production-report-v0.3",
        "status": status,
        "featureId": spec["proposedFeatureId"],
        "sourceFeatureId": spec["sourceFeatureId"],
        "productionStage": spec["productionStage"],
        "targetEpoch": profile["targetEpoch"],
        "orientation": frame.to_dict(),
        "orientationGate": orientation_gate,
        "evidence": evidence_report,
        "modelOriginUtm51": [round(v, 6) for v in projected["originUtm51"]],
        "qa": qa,
        "hardStops": [
            "Baker v0.3 is not survey-grade architecture.",
            "Do not call the current front orientation architecturally approved while policy remains a proxy.",
            "Do not infer interiors, basement/tunnels, or hidden structure.",
            "Replace roof envelope and facade proportions when stronger measured/recovered evidence becomes available."
        ],
    }
    return assemblies, report


def generate_baker_v03(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    assemblies, report = compile_baker_v03()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict[str, Any]] = {}
    for lod, assembly in assemblies.items():
        obj_path = output_dir / f"baker-hall-v0.3-{lod}.obj"
        obj_hash = write_obj_assembly(obj_path, assembly)
        part_records = []
        part_dir = output_dir / "meshparts" / lod
        for part in assembly.parts:
            part_path = part_dir / f"{part.name}.obj"
            write_obj(
                part_path,
                part.mesh,
                object_name=part.name,
                metadata_comments=(
                    f"featureId={assembly.feature_id}",
                    f"sourceFeatureId={assembly.source_feature_id or assembly.feature_id}",
                    f"lod={lod}",
                    f"materialClass={part.material_class}",
                    f"confidence={part.confidence}",
                    f"evidenceIds={','.join(part.evidence_ids)}",
                ),
            )
            part_records.append({
                "name": part.name,
                "path": f"{LOGICAL_OUTPUT_DIR}/meshparts/{lod}/{part.name}.obj",
                "sha256": _sha256(part_path),
                "triangleEquivalent": part.mesh.triangle_equivalent,
                "materialClass": part.material_class,
            })
        outputs[lod] = {
            "path": f"{LOGICAL_OUTPUT_DIR}/{obj_path.name}",
            "sha256": obj_hash,
            "triangleEquivalent": assembly.mesh.triangle_equivalent,
            "partNames": [part.name for part in assembly.parts],
            "meshParts": part_records,
        }

    spec = _read(SPEC_PATH)
    manifest = {
        "schemaVersion": "uplb-production-asset-manifest-v0.2",
        "assetId": spec["artifactContract"]["assetId"],
        "featureId": spec["proposedFeatureId"],
        "sourceFeatureId": spec["sourceFeatureId"],
        "productionStage": spec["productionStage"],
        "stableMeshNames": spec["artifactContract"]["stableMeshNames"],
        "lods": {key: value for key, value in outputs.items() if key.startswith("lod")},
        "collision": outputs["collision"],
        "exchange": {
            "preferred": spec["artifactContract"].get("preferredExchangeFormat", "undecided"),
            "robloxBakeoff": ["GLB", "FBX"],
            "reimportNamingPolicy": spec["artifactContract"]["reimportNamingPolicy"],
            "studioImportPresetDraft": spec["artifactContract"].get("studioImportPresetDraft"),
            "blenderExportStatus": "pending-local-blender",
        },
        "qa": report["qa"],
        "inputs": {
            "spec": {"path": str(SPEC_PATH.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha256(SPEC_PATH)},
            "referenceProfile": {"path": str(REFERENCE_PATH.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha256(REFERENCE_PATH)},
            "featureSnapshot": {"path": str(SNAPSHOT_PATH.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha256(SNAPSHOT_PATH)},
        },
        "visualReviewGate": "pending-human",
    }
    validate_schema(manifest, MANIFEST_SCHEMA, "Baker v0.3 asset manifest")
    manifest_path = output_dir / "asset-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report["outputs"] = outputs
    report["assetManifest"] = {
        "path": f"{LOGICAL_OUTPUT_DIR}/{manifest_path.name}",
        "sha256": _sha256(manifest_path),
    }
    report_path = output_dir / "production-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"report": report, "manifest": manifest, "manifestPath": manifest_path, "reportPath": report_path}


def main() -> int:
    result = generate_baker_v03()
    print(json.dumps({"status": result["report"]["status"], "visualReviewGate": result["manifest"]["visualReviewGate"]}, indent=2))
    return 0 if result["report"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
