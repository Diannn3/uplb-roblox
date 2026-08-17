from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon

from .assembly import AssemblyPart, BuildingAssembly, write_obj_assembly
from .mesh import (
    MeshData,
    extrude_polygon,
    gable_prism_mesh,
    oriented_box_mesh,
    oriented_cylinder_mesh,
    project_wgs84_ring_to_local_meters,
)
from .qa import validate_assembly_geometry
from .registry import ROOT

REFERENCE_PATH = ROOT / "data" / "modeling" / "reference" / "baker-hall.reference-profile.json"
SPEC_PATH = ROOT / "data" / "modeling" / "building-specs" / "baker-hall.v0.2.json"
CANONICAL_SNAPSHOT_PATH = ROOT / "data" / "modeling" / "reference" / "baker-canonical-snapshot.geojson"
OUTPUT_DIR = ROOT / "assets" / "generated" / "production" / "baker-hall"


class BakerHallError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _front_frame(ring: list[tuple[float, float]]) -> dict[str, Any]:
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.area <= 0:
        raise BakerHallError("Baker Hall canonical footprint is invalid")
    edge_rows: list[tuple[float, int, tuple[float, float], tuple[float, float]]] = []
    for index, start in enumerate(ring):
        end = ring[(index + 1) % len(ring)]
        length = math.dist(start, end)
        edge_rows.append((length, index, start, end))
    length, index, start, end = max(edge_rows, key=lambda row: row[0])
    dx, dy = end[0] - start[0], end[1] - start[1]
    tangent = (dx / length, dy / length)
    # For a CCW polygon the interior lies left of each directed edge, so the
    # outward normal is the right-hand normal. Reverse for CW rings.
    if polygon.exterior.is_ccw:
        outward = (tangent[1], -tangent[0])
    else:
        outward = (-tangent[1], tangent[0])
    midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    return {
        "edgeIndex": index,
        "lengthM": length,
        "start": start,
        "end": end,
        "midpoint": midpoint,
        "tangent": tangent,
        "outward": outward,
        "selectionMethod": "longest-single-canonical-edge; provisional front-edge proxy pending surveyed/model orientation",
    }


def _point(frame: dict[str, Any], along_m: float, outward_m: float, z_m: float) -> tuple[float, float, float]:
    mx, my = frame["midpoint"]
    tx, ty = frame["tangent"]
    nx, ny = frame["outward"]
    return (mx + tx * along_m + nx * outward_m, my + ty * along_m + ny * outward_m, z_m)


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
    notes: str = "",
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


def _cylinder_part(
    frame: dict[str, Any],
    name: str,
    *,
    radius: float,
    height: float,
    along: float,
    outward: float,
    z: float,
    material: str,
    confidence: str,
    evidence: tuple[str, ...],
) -> AssemblyPart:
    mesh = oriented_cylinder_mesh(
        radius,
        height,
        center=_point(frame, along, outward, z),
        tangent_xy=frame["tangent"],
        outward_xy=frame["outward"],
        segments=16,
    )
    return AssemblyPart(name, mesh, material, confidence, evidence)


def _wing_positions(front_length: float, portico_width: float, bay_count: int) -> tuple[float, ...]:
    if bay_count < 1:
        return ()
    half_front = front_length / 2.0
    half_portico = portico_width / 2.0
    outer_margin = 2.0
    inner_margin = 1.8
    left_min = -half_front + outer_margin
    left_max = -half_portico - inner_margin
    if left_max <= left_min:
        raise BakerHallError("front facade is too short for Baker wing bays")
    step = (left_max - left_min) / max(bay_count - 1, 1)
    left = [left_min + step * index for index in range(bay_count)] if bay_count > 1 else [(left_min + left_max) / 2]
    return tuple(left + [-value for value in reversed(left)])


def compile_baker_hall() -> tuple[BuildingAssembly, dict[str, Any]]:
    reference = _read_json(REFERENCE_PATH)
    spec = _read_json(SPEC_PATH)
    canonical = _read_json(CANONICAL_SNAPSHOT_PATH)
    if canonical.get("type") == "FeatureCollection":
        feature = canonical["features"][0]
    elif "feature" in canonical:
        feature = canonical["feature"]
    else:
        feature = canonical
    if feature.get("id") != "uplb:building:baker-hall":
        raise BakerHallError("canonical Baker Hall snapshot does not have the expected feature id")
    coordinates = feature["geometry"]["coordinates"][0]
    ring, origin = project_wgs84_ring_to_local_meters(coordinates)
    frame = _front_frame(ring)

    dimensions = spec["referenceDerivedApproximation"]
    body_height = float(dimensions["bodyHeightM"])
    floor_break = float(dimensions["groundFloorHeightM"])
    portico_width = float(dimensions["porticoWidthM"])
    portico_projection = float(dimensions["porticoProjectionM"])
    evidence_photos = tuple(reference["evidenceGroups"]["frontFacade"])
    evidence_canonical = ("source:canonical:osm-baker-way-37449973",)
    evidence_all = tuple(dict.fromkeys(evidence_canonical + evidence_photos))

    parts: list[AssemblyPart] = [
        AssemblyPart(
            "body-canonical-footprint",
            extrude_polygon(ring, body_height),
            "concrete-painted",
            "source-supported-footprint/provisional-height",
            evidence_canonical,
            "Canonical footprint is preserved. Height remains reference-derived until surveyed/recovered.",
        )
    ]

    # The front portico is the strongest visual identifier in every reviewed
    # front-facade photograph. Geometry is deliberately modular and removable.
    parts.append(
        _box_part(
            frame,
            "portico-balcony-slab",
            width=portico_width,
            depth=portico_projection,
            height=0.28,
            along=0.0,
            outward=portico_projection / 2.0,
            z=floor_break + 0.14,
            material="concrete-painted",
            confidence="high-visual",
            evidence=evidence_photos,
        )
    )
    column_positions = (-6.0, -2.0, 2.0, 6.0)
    for index, along in enumerate(column_positions, start=1):
        parts.append(
            _box_part(
                frame,
                f"ground-pier-{index:02d}",
                width=0.55,
                depth=0.55,
                height=floor_break,
                along=along,
                outward=portico_projection - 0.35,
                z=floor_break / 2.0,
                material="concrete-painted",
                confidence="medium-visual",
                evidence=evidence_photos,
                notes="Square lower supports are simplified from front photographic evidence.",
            )
        )
        upper_height = body_height - floor_break - 0.35
        parts.append(
            _cylinder_part(
                frame,
                f"upper-round-column-{index:02d}",
                radius=0.32,
                height=upper_height,
                along=along,
                outward=portico_projection - 0.35,
                z=floor_break + 0.28 + upper_height / 2.0,
                material="concrete-painted",
                confidence="high-visual",
                evidence=evidence_photos,
            )
        )

    # Balustrade: rails + repeated simple balusters. This is not a conservation
    # survey reproduction; dimensions are intentionally parametric/provisional.
    railing_outward = portico_projection + 0.02
    parts.extend(
        [
            _box_part(
                frame,
                "balustrade-bottom-rail",
                width=portico_width,
                depth=0.16,
                height=0.16,
                along=0.0,
                outward=railing_outward,
                z=floor_break + 0.38,
                material="concrete-painted",
                confidence="high-visual",
                evidence=evidence_photos,
            ),
            _box_part(
                frame,
                "balustrade-top-rail",
                width=portico_width,
                depth=0.18,
                height=0.18,
                along=0.0,
                outward=railing_outward,
                z=floor_break + 1.15,
                material="concrete-painted",
                confidence="high-visual",
                evidence=evidence_photos,
            ),
        ]
    )
    for index in range(22):
        along = -portico_width / 2.0 + 0.65 + index * (portico_width - 1.3) / 21.0
        parts.append(
            _box_part(
                frame,
                f"baluster-{index + 1:02d}",
                width=0.12,
                depth=0.12,
                height=0.72,
                along=along,
                outward=railing_outward,
                z=floor_break + 0.765,
                material="concrete-painted",
                confidence="medium-visual",
                evidence=evidence_photos,
            )
        )

    # Wing facade: the repeated grid, horizontal bands, and metal awnings are
    # visible in multiple eras of imagery; exact bay dimensions remain unverified.
    bay_positions = _wing_positions(frame["lengthM"], portico_width, int(dimensions["wingBayCountEachSide"]))
    for floor_index, (window_z, awning_z) in enumerate(((2.05, 3.12), (5.95, 7.05)), start=1):
        for bay_index, along in enumerate(bay_positions, start=1):
            parts.append(
                _box_part(
                    frame,
                    f"wing-window-f{floor_index}-{bay_index:02d}",
                    width=2.65,
                    depth=0.10,
                    height=1.55,
                    along=along,
                    outward=0.06,
                    z=window_z,
                    material="painted-metal-glass",
                    confidence="medium-visual",
                    evidence=evidence_photos,
                    notes="Window opening is a reference-derived panel, not a surveyed frame profile.",
                )
            )
            parts.append(
                _box_part(
                    frame,
                    f"wing-awning-f{floor_index}-{bay_index:02d}",
                    width=3.0,
                    depth=0.78,
                    height=0.12,
                    along=along,
                    outward=0.42,
                    z=awning_z,
                    material="painted-metal",
                    confidence="high-visual",
                    evidence=evidence_photos,
                )
            )

    # Repeated pilasters/corner strips and strong floor/cornice bands establish
    # the prewar facade rhythm without claiming ornamental survey accuracy.
    separator_positions = []
    half_front = frame["lengthM"] / 2.0
    for sign in (-1.0, 1.0):
        separator_positions.extend(
            [
                sign * (portico_width / 2.0 + 0.55),
                sign * (portico_width / 2.0 + 5.0),
                sign * (portico_width / 2.0 + 9.5),
                sign * (half_front - 0.45),
            ]
        )
    for index, along in enumerate(sorted(separator_positions), start=1):
        parts.append(
            _box_part(
                frame,
                f"front-pilaster-{index:02d}",
                width=0.42,
                depth=0.24,
                height=body_height - 0.35,
                along=along,
                outward=0.13,
                z=(body_height - 0.35) / 2.0,
                material="concrete-painted",
                confidence="medium-visual",
                evidence=evidence_photos,
            )
        )
    for name, z, height in (("floor-string-course", floor_break, 0.28), ("upper-cornice", body_height - 0.35, 0.32)):
        parts.append(
            _box_part(
                frame,
                name,
                width=frame["lengthM"] + 0.4,
                depth=0.28,
                height=height,
                along=0.0,
                outward=0.14,
                z=z,
                material="concrete-painted",
                confidence="high-visual",
                evidence=evidence_photos,
            )
        )

    # Central door/window recess panels behind the portico.
    for index, along in enumerate((-3.2, 0.0, 3.2), start=1):
        parts.append(
            _box_part(
                frame,
                f"central-door-{index:02d}",
                width=2.45,
                depth=0.08,
                height=2.8,
                along=along,
                outward=0.05,
                z=1.55,
                material="wood-metal",
                confidence="medium-visual",
                evidence=evidence_photos,
            )
        )
        parts.append(
            _box_part(
                frame,
                f"central-upper-opening-{index:02d}",
                width=2.45,
                depth=0.08,
                height=2.3,
                along=along,
                outward=0.05,
                z=5.95,
                material="painted-metal-glass",
                confidence="medium-visual",
                evidence=evidence_photos,
            )
        )

    # Portico entablature and the distinctive central parapet/sign block.
    parts.append(
        _box_part(
            frame,
            "portico-entablature",
            width=portico_width + 1.0,
            depth=portico_projection + 0.25,
            height=0.42,
            along=0.0,
            outward=portico_projection / 2.0,
            z=body_height - 0.25,
            material="concrete-painted",
            confidence="high-visual",
            evidence=evidence_photos,
        )
    )
    parts.extend(
        [
            _box_part(
                frame,
                "central-sign-parapet",
                width=portico_width + 0.5,
                depth=0.42,
                height=1.35,
                along=0.0,
                outward=0.18,
                z=body_height + 0.62,
                material="concrete-painted",
                confidence="high-visual",
                evidence=evidence_photos,
                notes="Sign lettering is intentionally omitted from geometry v0.2.",
            ),
            _box_part(
                frame,
                "central-sign-parapet-cap",
                width=portico_width + 1.0,
                depth=0.56,
                height=0.18,
                along=0.0,
                outward=0.20,
                z=body_height + 1.37,
                material="concrete-painted",
                confidence="medium-visual",
                evidence=evidence_photos,
            ),
        ]
    )

    # A shallow central gable is visible behind/above the historic facade in
    # reference imagery. Its exact ridge/eave geometry is not survey-verified.
    roof_depth = float(dimensions["centralRoofDepthM"])
    roof_center = _point(frame, 0.0, -roof_depth / 2.0 + 0.5, 0.0)
    parts.append(
        AssemblyPart(
            "central-provisional-gable-roof",
            gable_prism_mesh(
                float(dimensions["centralRoofWidthM"]),
                roof_depth,
                eave_z=body_height - 0.05,
                ridge_z=float(dimensions["ridgeHeightM"]),
                center_xy=(roof_center[0], roof_center[1]),
                tangent_xy=frame["tangent"],
                outward_xy=frame["outward"],
            ),
            "corrugated-metal",
            "medium-low-visual",
            evidence_photos,
            "Provisional low-poly roof inferred from visible roof silhouette; replace after recovered model/survey evidence.",
        )
    )

    assembly = BuildingAssembly("uplb:building:baker-hall", "baker-exterior-v0.2-reference-derived", tuple(parts))
    assembly.validate()
    qa = validate_assembly_geometry(assembly, triangle_budget=90000)
    report = {
        "schemaVersion": "uplb-baker-production-report-v0.2",
        "status": "reference-derived-prototype",
        "featureId": assembly.feature_id,
        "modelVersion": assembly.version,
        "canonicalOriginUtm51": [round(origin[0], 6), round(origin[1], 6)],
        "frontFacade": {
            "canonicalEdgeIndex": frame["edgeIndex"],
            "lengthM": round(frame["lengthM"], 6),
            "selectionMethod": frame["selectionMethod"],
            "porticoWidthM": portico_width,
            "porticoRatio": round(portico_width / frame["lengthM"], 6),
        },
        "assembly": assembly.summary(),
        "qa": qa,
        "evidence": reference,
        "accuracyClaims": {
            "footprintPlacement": "source-supported canonical input",
            "frontFacadeComposition": "reference-derived from multiple public photographs",
            "exactFacadeDimensions": "not surveyed",
            "roofGeometry": "provisional",
            "interior": "not modeled",
        },
        "hardStops": [
            "Do not call this a survey-accurate reconstruction.",
            "Do not model interiors from inference.",
            "Replace provisional roof/facade dimensions if the 2014 model, drawings, or field measurements are recovered.",
        ],
    }
    return assembly, report


def generate_baker_hall_outputs(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    assembly, report = compile_baker_hall()
    output_dir.mkdir(parents=True, exist_ok=True)
    obj_path = output_dir / "baker-hall-v0.2.obj"
    obj_hash = write_obj_assembly(obj_path, assembly)
    report["output"] = {
        "objPath": str(obj_path.relative_to(ROOT)).replace("\\", "/"),
        "objSha256": obj_hash,
    }
    qa_path = output_dir / "baker-hall-v0.2.qa.json"
    qa_path.write_text(json.dumps(report["qa"], indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report["output"]["qaPath"] = str(qa_path.relative_to(ROOT)).replace("\\", "/")
    report["output"]["qaSha256"] = "sha256:" + hashlib.sha256(qa_path.read_bytes()).hexdigest()
    report_path = output_dir / "baker-hall-v0.2.report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report["output"]["reportPath"] = str(report_path.relative_to(ROOT)).replace("\\", "/")
    report["output"]["reportSha256"] = "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
    return report


def main() -> int:
    report = generate_baker_hall_outputs()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
