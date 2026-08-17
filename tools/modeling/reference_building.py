from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from shapely.geometry import Polygon

from .assembly import AssemblyPart, BuildingAssembly, write_obj_assembly
from .budgets import budget_for
from .mesh import extrude_polygon, oriented_box_mesh, project_wgs84_ring_to_local_meters
from .qa import validate_assembly_geometry
from .registry import ROOT

SPEC_DIR = ROOT / "data" / "modeling" / "building-specs" / "central-wave"
OUTPUT_ROOT = ROOT / "assets" / "generated" / "production" / "central-wave"
SPEC_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "reference-building-production-spec.schema.json"
REFERENCE_SCHEMA = ROOT / "data" / "canonical" / "schemas" / "building-reference-profile.schema.json"


class ReferenceBuildingError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_json(instance: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = _read_json(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        raise ReferenceBuildingError(label + " schema failure: " + "; ".join(error.message for error in errors))


def _edge_frame(ring: list[tuple[float, float]], index: int) -> dict[str, Any]:
    polygon = Polygon(ring)
    start = ring[index]
    end = ring[(index + 1) % len(ring)]
    length = math.dist(start, end)
    if length <= 0:
        raise ReferenceBuildingError("zero-length facade edge")
    tangent = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
    outward = (tangent[1], -tangent[0]) if polygon.exterior.is_ccw else (-tangent[1], tangent[0])
    return {
        "edgeIndex": index,
        "lengthM": length,
        "start": start,
        "end": end,
        "midpoint": ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0),
        "tangent": tangent,
        "outward": outward,
    }


def _front_frame(ring: list[tuple[float, float]]) -> dict[str, Any]:
    frames = [_edge_frame(ring, index) for index in range(len(ring))]
    frame = max(frames, key=lambda item: item["lengthM"])
    frame["selectionMethod"] = "longest-edge-proxy; deterministic production orientation only, not surveyed entrance orientation"
    return frame


def _point(frame: dict[str, Any], along: float, outward: float, z: float) -> tuple[float, float, float]:
    mx, my = frame["midpoint"]
    tx, ty = frame["tangent"]
    nx, ny = frame["outward"]
    return (mx + tx * along + nx * outward, my + ty * along + ny * outward, z)


def _box_part(
    frame: dict[str, Any],
    name: str,
    *,
    width: float,
    depth: float,
    height: float,
    along: float,
    outward: float,
    z: float,
    material: str,
    confidence: str,
    evidence: tuple[str, ...],
    notes: str,
) -> AssemblyPart:
    mesh = oriented_box_mesh(
        width,
        depth,
        height,
        center=_point(frame, along, outward, z),
        tangent_xy=frame["tangent"],
        outward_xy=frame["outward"],
    )
    return AssemblyPart(name, mesh, material, confidence, evidence, notes)


def _numeric_levels(feature: dict[str, Any]) -> float | None:
    attrs = feature.get("properties", {}).get("attributes", {})
    raw = attrs.get("building:levels") or attrs.get("levels")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _add_perimeter_bands(
    parts: list[AssemblyPart],
    ring: list[tuple[float, float]],
    *,
    levels: float | None,
    height: float,
    band_depth: float,
    evidence: tuple[str, ...],
) -> None:
    if not levels or levels <= 1:
        return
    integer_breaks = range(1, max(int(math.floor(levels)), 1))
    for level_index in integer_breaks:
        z = height * (level_index / levels)
        for edge_index in range(len(ring)):
            frame = _edge_frame(ring, edge_index)
            if frame["lengthM"] < 1.0:
                continue
            parts.append(
                _box_part(
                    frame,
                    f"floor-band-l{level_index:02d}-e{edge_index:02d}",
                    width=max(frame["lengthM"] - 0.06, 0.2),
                    depth=band_depth,
                    height=0.16,
                    along=0.0,
                    outward=band_depth / 2.0 + 0.01,
                    z=z,
                    material="concrete-painted",
                    confidence="source-level-count/proxy-detail",
                    evidence=evidence,
                    notes="Procedural level break; not a measured facade molding.",
                )
            )


def _add_front_bays(
    parts: list[AssemblyPart],
    frame: dict[str, Any],
    *,
    preset: str,
    bay_count: int,
    body_height: float,
    levels: float | None,
    panel_height: float,
    panel_width_ratio: float,
    panel_depth: float,
    support_width: float,
    evidence: tuple[str, ...],
    confidence: str,
) -> None:
    if preset == "massing-only" or bay_count <= 0:
        return
    facade_width = frame["lengthM"] * 0.84
    slot = facade_width / bay_count
    panel_width = max(slot * panel_width_ratio, 0.25)
    left = -facade_width / 2.0 + slot / 2.0
    outward = panel_depth / 2.0 + 0.03
    if preset == "academic-banded":
        floors = max(int(round(levels or 2)), 1)
        floor_height = body_height / floors
        usable_panel_height = min(panel_height, max(floor_height * 0.55, 0.6))
        for floor in range(floors):
            z = floor_height * floor + floor_height * 0.55
            for bay in range(bay_count):
                parts.append(
                    _box_part(
                        frame,
                        f"front-window-f{floor+1:02d}-b{bay+1:02d}",
                        width=panel_width,
                        depth=panel_depth,
                        height=usable_panel_height,
                        along=left + bay * slot,
                        outward=outward,
                        z=z,
                        material="painted-metal-glass",
                        confidence=confidence,
                        evidence=evidence,
                        notes="Reference/source-tag-informed facade proxy on provisional front edge; not a measured opening.",
                    )
                )
        return

    # Modernist glass-frame/auditorium proxy: broad full-height glazing plus
    # concrete vertical supports. We intentionally do not cut openings into the
    # canonical massing body in this evidence stage.
    glazed_height = min(panel_height, body_height - 0.8)
    z = max(glazed_height / 2.0 + 0.35, body_height / 2.0)
    for bay in range(bay_count):
        parts.append(
            _box_part(
                frame,
                f"front-glass-b{bay+1:02d}",
                width=panel_width,
                depth=panel_depth,
                height=glazed_height,
                along=left + bay * slot,
                outward=outward,
                z=z,
                material="painted-metal-glass",
                confidence=confidence,
                evidence=evidence,
                notes="Visual/source-informed glass-panel proxy; exact grid and entrance placement remain unresolved.",
            )
        )
    for support in range(bay_count + 1):
        along = -facade_width / 2.0 + support * slot
        parts.append(
            _box_part(
                frame,
                f"front-support-{support+1:02d}",
                width=support_width,
                depth=max(panel_depth * 1.7, 0.16),
                height=max(body_height - 0.35, 0.5),
                along=along,
                outward=max(panel_depth, 0.08) / 2.0 + 0.04,
                z=body_height / 2.0,
                material="concrete-painted",
                confidence=confidence,
                evidence=evidence,
                notes="Modernist frame proxy; placement follows deterministic provisional facade edge.",
            )
        )


def compile_reference_building(spec_path: Path) -> tuple[BuildingAssembly, dict[str, Any]]:
    spec_path = Path(spec_path)
    spec = _read_json(spec_path)
    _validate_json(spec, SPEC_SCHEMA, spec_path.name)
    feature_path = ROOT / spec["featureSnapshot"]
    feature = _read_json(feature_path)
    if feature.get("id") != spec["sourceFeatureId"]:
        raise ReferenceBuildingError(f"{spec_path.name}: sourceFeatureId does not match feature snapshot")
    reference_path = ROOT / spec.get("referenceProfile", "")
    reference = _read_json(reference_path) if reference_path.is_file() else None
    if reference:
        _validate_json(reference, REFERENCE_SCHEMA, reference_path.name)
        if reference.get("featureId") != spec["proposedFeatureId"]:
            raise ReferenceBuildingError(f"{spec_path.name}: proposedFeatureId does not match reference profile")
    coordinates = feature["geometry"]["coordinates"][0]
    ring, origin = project_wgs84_ring_to_local_meters(coordinates)
    polygon = Polygon(ring)
    body_height = float(spec["height"]["meters"])
    evidence = tuple(spec.get("referenceIds", []))
    body_material = spec["materials"][0]
    parts: list[AssemblyPart] = [
        AssemblyPart(
            "body-source-footprint",
            extrude_polygon(ring, body_height),
            body_material,
            f"source-supported-footprint/{spec['height']['confidence']}-height",
            evidence,
            "Footprint comes from the pinned project candidate snapshot. Production ID is not a canonical promotion.",
        )
    ]
    levels = _numeric_levels(feature)
    facade = spec["facade"]
    preset = facade["preset"]
    if preset in {"academic-banded", "glass-frame"}:
        _add_perimeter_bands(
            parts,
            ring,
            levels=levels,
            height=body_height,
            band_depth=float(facade.get("bandDepthM", 0.18)),
            evidence=evidence,
        )
    frame = _front_frame(ring)
    _add_front_bays(
        parts,
        frame,
        preset=preset,
        bay_count=int(facade.get("bayCount", 0)),
        body_height=body_height,
        levels=levels,
        panel_height=float(facade.get("panelHeightM", 1.2)),
        panel_width_ratio=float(facade.get("panelWidthRatio", 0.72)),
        panel_depth=float(facade.get("panelDepthM", 0.08)),
        support_width=float(facade.get("supportWidthM", 0.28)),
        evidence=evidence,
        confidence=str(facade["confidence"]),
    )
    assembly = BuildingAssembly(
        spec["proposedFeatureId"],
        f"{spec_path.stem}-reference-production",
        tuple(parts),
        source_feature_id=spec["sourceFeatureId"],
        identity_status=spec["identityStatus"],
    )
    assembly.validate()
    budget = budget_for(spec["productionTier"])
    qa = validate_assembly_geometry(assembly, triangle_budget=budget.lod0_triangles)
    report = {
        "schemaVersion": "uplb-reference-building-production-report-v0.1",
        "status": "reference-derived-prototype" if qa["status"] == "pass" else "fail",
        "name": spec["name"],
        "featureId": assembly.feature_id,
        "sourceFeatureId": assembly.source_feature_id,
        "identityStatus": assembly.identity_status,
        "modelVersion": assembly.version,
        "originUtm51": [round(origin[0], 6), round(origin[1], 6)],
        "footprintAreaM2": round(float(polygon.area), 3),
        "frontFacadeProxy": {
            "edgeIndex": frame["edgeIndex"],
            "lengthM": round(frame["lengthM"], 3),
            "selectionMethod": frame["selectionMethod"],
        },
        "height": spec["height"],
        "facade": spec["facade"],
        "roof": spec["roof"],
        "assembly": assembly.summary(),
        "qa": qa,
        "accuracyClaims": spec["accuracyClaims"],
        "hardStops": [
            "Do not treat proposedFeatureId as canonical identity promotion.",
            "Do not call this a survey-accurate architectural reconstruction.",
            "Do not infer interiors from exterior massing or photographs.",
            "Replace proxy facade orientation/dimensions when recovered models, drawings, or measurements become available.",
        ],
        "inputs": {
            "spec": {"path": str(spec_path.relative_to(ROOT)).replace('\\', '/'), "sha256": _sha256(spec_path)},
            "featureSnapshot": {"path": spec["featureSnapshot"], "sha256": _sha256(feature_path)},
            "referenceProfile": {"path": str(reference_path.relative_to(ROOT)).replace('\\', '/') if reference else None, "sha256": _sha256(reference_path) if reference else None},
        },
    }
    return assembly, report


def generate_reference_building_outputs(spec_path: Path, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    assembly, report = compile_reference_building(spec_path)
    slug = Path(spec_path).stem.replace(".v0", "-v0")
    output_dir = output_root / Path(spec_path).stem.split(".v")[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    obj_path = output_dir / f"{slug}.obj"
    obj_hash = write_obj_assembly(obj_path, assembly)
    qa_path = output_dir / f"{slug}.qa.json"
    report_path = output_dir / f"{slug}.report.json"
    report["output"] = {
        "objPath": str(obj_path.relative_to(ROOT)).replace('\\', '/'),
        "objSha256": obj_hash,
        "qaPath": str(qa_path.relative_to(ROOT)).replace('\\', '/'),
        "reportPath": str(report_path.relative_to(ROOT)).replace('\\', '/'),
    }
    qa_path.write_text(json.dumps(report["qa"], indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report["output"]["qaSha256"] = _sha256(qa_path)
    report["output"]["reportSha256"] = _sha256(report_path)
    return report


def generate_central_wave_outputs(spec_dir: Path = SPEC_DIR) -> list[dict[str, Any]]:
    reports = [generate_reference_building_outputs(path) for path in sorted(Path(spec_dir).glob("*.json"))]
    manifest = {
        "schemaVersion": "uplb-central-wave-production-manifest-v0.1",
        "generatedAt": "2026-08-17",
        "policy": {
            "identity": "Production feature IDs remain proposed/reviewed-candidate handles unless separately promoted through canonical review.",
            "geometry": "Pinned project candidate footprints are preserved; facade orientation/details are explicitly provisional unless supported by stronger evidence.",
            "photoBinaries": "No third-party reference-photo binaries are stored in this generated asset layer.",
        },
        "records": [
            {
                "featureId": row["featureId"],
                "sourceFeatureId": row["sourceFeatureId"],
                "identityStatus": row["identityStatus"],
                "name": row["name"],
                "status": row["status"],
                "objPath": row["output"]["objPath"],
                "objSha256": row["output"]["objSha256"],
                "qaPath": row["output"]["qaPath"],
                "qaStatus": row["qa"]["status"],
                "triangleEquivalent": row["assembly"]["triangleEquivalent"],
                "partCount": row["assembly"]["partCount"],
                "heightConfidence": row["height"]["confidence"],
                "facadeConfidence": row["facade"]["confidence"],
                "roofPolicy": row["roof"]["geometryPolicy"],
            }
            for row in reports
        ],
    }
    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return reports


def main() -> int:
    reports = generate_central_wave_outputs()
    print(json.dumps({"status": "pass" if all(row["status"] != "fail" for row in reports) else "fail", "reports": reports}, indent=2))
    return 0 if all(row["status"] != "fail" for row in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
