"""Build and export one evidence-aware production building inside Blender.

Run from Blender, for example:

    blender --background --python-exit-code 10 --python tools/blender/build_production_asset.py -- \\
      --asset-manifest assets/generated/production/baker-hall-v0.3/asset-manifest.json \\
      --output assets/generated/production/baker-hall-v0.3/blender

The script parses the deterministic per-MeshPart OBJ artifacts itself instead
of relying on Blender's OBJ axis-conversion defaults. The model coordinate
contract stays X=east, Y=north, Z=up, in metres. Blender and exported exchange
files are consumers; the JSON spec/manifest and geodata remain authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import bpy  # type: ignore
except ImportError as exc:  # pragma: no cover - only available inside Blender
    raise RuntimeError("build_production_asset.py must run inside Blender") from exc

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_VERSION = "uplb-blender-production-asset-v0.1"
PER_MESH_TRIANGLE_LIMIT = 20_000


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _parse_obj(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields[0] == "v" and len(fields) >= 4:
            vertices.append((float(fields[1]), float(fields[2]), float(fields[3])))
        elif fields[0] == "f" and len(fields) >= 4:
            indices: list[int] = []
            for token in fields[1:]:
                # OBJ supports v/vt/vn; generated Wave 02 meshes currently use v only.
                vertex_token = token.split("/", 1)[0]
                index = int(vertex_token)
                if index < 0:
                    index = len(vertices) + index + 1
                indices.append(index - 1)
            faces.append(tuple(indices))
    if not vertices or not faces:
        raise ValueError(f"OBJ contains no usable mesh data: {path}")
    return vertices, faces


def _triangle_equivalent(faces: list[tuple[int, ...]]) -> int:
    return sum(max(len(face) - 2, 0) for face in faces)


def _material(name: str):
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    material = bpy.data.materials.new(name=name)
    material.diffuse_color = (0.6, 0.6, 0.6, 1.0)
    material.use_nodes = True
    return material


def _create_object(
    *,
    obj_path: Path,
    name: str,
    collection,
    material_class: str,
    custom_properties: dict[str, Any],
):
    vertices, faces = _parse_obj(obj_path)
    triangles = _triangle_equivalent(faces)
    if triangles > PER_MESH_TRIANGLE_LIMIT:
        raise ValueError(f"{name} has {triangles} triangles; Roblox per-mesh limit is {PER_MESH_TRIANGLE_LIMIT}")
    mesh = bpy.data.meshes.new(f"{name}__Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(_material(material_class))
    for key, value in custom_properties.items():
        obj[key] = value
    obj["TriangleEquivalent"] = triangles
    obj["SourceObjSha256"] = _sha256(obj_path)
    return obj, triangles


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)
    default = bpy.data.collections.get("Collection")
    if default:
        for obj in list(default.objects):
            default.objects.unlink(obj)


def _collection(name: str):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def _select_only(objects: list[Any]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def _export_gltf(path: Path, objects: list[Any]) -> None:
    _select_only(objects)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_extras=True,
        export_yup=True,
        export_apply=True,
    )


def _export_fbx(path: Path, objects: list[Any]) -> None:
    _select_only(objects)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="Z",
        axis_up="Y",
        add_leaf_bones=False,
        use_custom_props=True,
        bake_anim=False,
    )


def build(asset_manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    asset_manifest_path = Path(asset_manifest_path).resolve()
    output_dir = Path(output_dir).resolve()
    manifest = _read(asset_manifest_path)
    _clear_scene()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    # The authoritative asset remains in metres. Roblox Studio must import the
    # exchange file using the file unit that matches the authored metric data;
    # the later disposable-Studio bakeoff freezes the exact importer preset.
    # Axis export follows Roblox current guidance: Z Forward, Y Up. GlTF uses
    # its standard +Y-up convention.

    root_collection = _collection(manifest["assetId"])
    created: dict[str, list[Any]] = {}
    qa_rows: list[dict[str, Any]] = []
    stable_names = set(manifest["stableMeshNames"])

    for lod_name in ("lod0", "lod1", "lod2", "lod3"):
        record = manifest["lods"].get(lod_name)
        if not record:
            continue
        collection = _collection(f"{manifest['assetId']}__{lod_name.upper()}")
        objects: list[Any] = []
        for part in record.get("meshParts", []):
            name = part["name"]
            if name not in stable_names:
                raise ValueError(f"mesh part {name} is not declared in stableMeshNames")
            obj, triangles = _create_object(
                obj_path=_repo_path(part["path"]),
                name=name,
                collection=collection,
                material_class=part.get("materialClass", "default"),
                custom_properties={
                    "FeatureId": manifest["featureId"],
                    "SourceFeatureId": manifest["sourceFeatureId"],
                    "AssetId": manifest["assetId"],
                    "ProductionStage": manifest["productionStage"],
                    "LOD": lod_name,
                    "StableMeshName": name,
                    "GeneratorVersion": GENERATOR_VERSION,
                },
            )
            objects.append(obj)
            qa_rows.append({"lod": lod_name, "name": name, "triangleEquivalent": triangles, "status": "pass"})
        created[lod_name] = objects

    collision_record = manifest.get("collision") or {}
    collision_collection = _collection(f"{manifest['assetId']}__COLLISION")
    collision_objects: list[Any] = []
    for part in collision_record.get("meshParts", []):
        name = part["name"]
        obj, triangles = _create_object(
            obj_path=_repo_path(part["path"]),
            name=name,
            collection=collision_collection,
            material_class="collision-proxy",
            custom_properties={
                "FeatureId": manifest["featureId"],
                "SourceFeatureId": manifest["sourceFeatureId"],
                "AssetId": manifest["assetId"],
                "ProductionStage": manifest["productionStage"],
                "LOD": "collision",
                "StableMeshName": name,
                "GeneratorVersion": GENERATOR_VERSION,
                "CollisionProxy": True,
            },
        )
        obj.hide_render = True
        collision_objects.append(obj)
        qa_rows.append({"lod": "collision", "name": name, "triangleEquivalent": triangles, "status": "pass"})
    created["collision"] = collision_objects

    # Stamp scene-level provenance as well. The JSON source remains authoritative.
    scene = bpy.context.scene
    scene["AssetId"] = manifest["assetId"]
    scene["FeatureId"] = manifest["featureId"]
    scene["SourceFeatureId"] = manifest["sourceFeatureId"]
    scene["ProductionStage"] = manifest["productionStage"]
    scene["AssetManifestSha256"] = _sha256(asset_manifest_path)
    scene["GeneratorVersion"] = GENERATOR_VERSION
    scene["CoordinateContract"] = "X=east,Y=north,Z=up,meters"

    output_dir.mkdir(parents=True, exist_ok=True)
    blend_path = output_dir / f"{manifest['assetId']}.blend"
    exports: dict[str, Any] = {}
    for lod_name in ("lod0", "lod1", "lod2", "lod3"):
        objects = created.get(lod_name, [])
        if not objects:
            continue
        glb_path = output_dir / f"{manifest['assetId']}__{lod_name.upper()}.glb"
        fbx_path = output_dir / f"{manifest['assetId']}__{lod_name.upper()}.fbx"
        _export_gltf(glb_path, objects)
        _export_fbx(fbx_path, objects)
        exports[lod_name] = {
            "glb": {"path": glb_path.as_posix(), "sha256": _sha256(glb_path)},
            "fbx": {"path": fbx_path.as_posix(), "sha256": _sha256(fbx_path)},
        }

    collision_glb = output_dir / f"{manifest['assetId']}__COLLISION.glb"
    if collision_objects:
        _export_gltf(collision_glb, collision_objects)
        exports["collision"] = {"glb": {"path": collision_glb.as_posix(), "sha256": _sha256(collision_glb)}}

    # Default review visibility: only LOD0. Alternate LODs and collision
    # stay in the .blend for inspection/export but do not clutter review.
    for lod_name, objects in created.items():
        visible = lod_name == "lod0"
        for obj in objects:
            obj.hide_render = not visible
            obj.hide_set(not visible)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    qa = {
        "status": "pass",
        "generatorVersion": GENERATOR_VERSION,
        "blenderVersion": bpy.app.version_string,
        "assetId": manifest["assetId"],
        "coordinateContract": "Blender master: X=east,Y=north,Z=up,meters; exchange: Z Forward,Y Up with metric source scale",
        "studioImportContract": {
            "worldForward": "Front",
            "worldUp": "Top",
            "scaleUnitPolicy": "match-authored-metric-source; freeze exact preset during disposable-Studio bakeoff",
            "mergeMeshes": False,
            "useImportedPivot": True,
            "status": "pending-disposable-studio-bakeoff",
        },
        "perMeshTriangleLimit": PER_MESH_TRIANGLE_LIMIT,
        "meshRows": qa_rows,
        "stableNamesPresent": sorted({row["name"] for row in qa_rows}),
        "blend": {"path": blend_path.as_posix(), "sha256": _sha256(blend_path)},
        "exports": exports,
        "visualReviewGate": "pending-human",
        "studioImportBakeoff": "pending-disposable-studio",
    }
    _write(output_dir / "blender-production-qa.json", qa)
    return qa


def _args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = _args(argv)
    qa = build(args.asset_manifest, args.output)
    print(json.dumps(qa, indent=2, sort_keys=True))
    return 0 if qa["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
