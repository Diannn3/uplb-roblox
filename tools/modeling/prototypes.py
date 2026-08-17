from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mesh import box_mesh, cylinder_mesh, extrude_polygon, project_wgs84_ring_to_local_meters, write_obj

ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def generate_baker_massing(
    snapshot_path: Path = ROOT / "data" / "modeling" / "reference" / "baker-canonical-snapshot.geojson",
    spec_path: Path = ROOT / "data" / "modeling" / "building-specs" / "baker-hall.v0.1.json",
    output_path: Path = ROOT / "assets" / "generated" / "prototypes" / "baker-hall-massing.obj",
) -> dict[str, Any]:
    snapshot = _read(snapshot_path)
    spec = _read(spec_path)
    feature = snapshot["feature"]
    ring = feature["geometry"]["coordinates"][0]
    local_ring, utm_centroid = project_wgs84_ring_to_local_meters(ring)
    height = float(spec["prototype"]["heightM"])
    mesh = extrude_polygon(local_ring, height)
    write_obj(
        output_path,
        mesh,
        object_name="BLDG_Baker_Massing",
        metadata_comments=[
            f"FeatureId={spec['featureId']}",
            f"HeightMethod={spec['prototype']['heightMethod']}",
            "Status=prototype-not-architectural-truth",
        ],
    )
    meta = {
        "schemaVersion": "uplb-prototype-mesh-v0.1",
        "featureId": spec["featureId"],
        "sourceSnapshot": _display_path(snapshot_path),
        "output": _display_path(output_path),
        "utmCentroidEastingM": round(utm_centroid[0], 6),
        "utmCentroidNorthingM": round(utm_centroid[1], 6),
        "heightM": height,
        "vertexCount": len(mesh.vertices),
        "faceCount": len(mesh.faces),
        "triangleEquivalent": mesh.triangle_equivalent,
        "claim": "massing-only; footprint is source-supported, facade/roof/detail are not verified",
    }
    meta_path = output_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def generate_kit_prototypes(
    kit_path: Path = ROOT / "data" / "modeling" / "architecture-kit-v0.1.json",
    output_dir: Path = ROOT / "assets" / "uplb-kit" / "prototypes",
) -> list[dict[str, Any]]:
    kit = _read(kit_path)
    selected = {
        "window:jalousie-a",
        "column:concrete-square-a",
        "column:concrete-round-a",
        "shade:horizontal-deep-a",
        "bench:campus-a",
        "bollard:campus-a",
        "utility:box-a",
        "column:concrete-round-baker-a",
        "column:concrete-square-baker-a",
        "awning:green-metal-baker-a",
        "window:historic-baker-panel-a",
        "door:historic-baker-panel-a",
    }
    reports=[]
    for component in kit["components"]:
        if component["id"] not in selected:
            continue
        width, depth, height = map(float, component["defaultDimensionsM"])
        if component["id"] in {"column:concrete-round-a", "column:concrete-round-baker-a", "bollard:campus-a"}:
            mesh = cylinder_mesh(max(width, depth)/2, height, 12)
        else:
            mesh = box_mesh(width, depth, height)
        safe = component["id"].replace(":", "_").replace("/", "_")
        path = output_dir / f"{safe}.obj"
        write_obj(path, mesh, object_name=safe, metadata_comments=[f"AssetKitId={component['id']}","Status=dimension-prototype"])
        reports.append({"id":component["id"],"path":_display_path(path),"vertices":len(mesh.vertices),"triangleEquivalent":mesh.triangle_equivalent})
    manifest={"schemaVersion":"uplb-kit-prototype-manifest-v0.1","generated":reports,"claim":"Primitive dimension prototypes only; visual design pending reference validation."}
    (output_dir/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return reports
