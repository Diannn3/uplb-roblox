"""Replace a greybox building with a production asset in an existing Blender campus scene.

This is a review/diagnostic consumer only. Canonical scene placement and the
production placement binding remain authoritative.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    import bpy  # type: ignore
except ImportError as exc:
    raise RuntimeError("preview_production_asset.py must run inside Blender") from exc

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.blender.build_production_asset import _create_object, _read, _repo_path  # noqa: E402


def _collection(name: str):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def build_preview(base_blend: Path, asset_manifest: Path, placement_binding: Path, output: Path) -> dict[str, Any]:
    base_blend = base_blend.resolve()
    asset_manifest = asset_manifest.resolve()
    placement_binding = placement_binding.resolve()
    output = output.resolve()

    bpy.ops.wm.open_mainfile(filepath=str(base_blend))
    manifest = _read(asset_manifest)
    binding = _read(placement_binding)

    if binding["featureId"] != manifest["featureId"]:
        raise ValueError("asset manifest and placement binding FeatureId mismatch")
    if binding["assetId"] != manifest["assetId"]:
        raise ValueError("asset manifest and placement binding AssetId mismatch")
    if binding["softwareTransformValidation"]["status"] != "pass":
        raise ValueError("placement binding software-transform validation must pass")

    feature_id = manifest["featureId"]
    existing_proxy_objects = [
        obj for obj in list(bpy.data.objects)
        if obj.get("FeatureId") == feature_id
    ]
    for obj in existing_proxy_objects:
        obj.hide_render = True
        obj.hide_set(True)

    collection = _collection(f"ProductionPreview__{manifest['assetId']}")
    root = bpy.data.objects.new(f"{manifest['assetId']}__ROOT", None)
    collection.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"

    translation = binding["sceneTransform"]["translationLocalMeters"]
    rotation = binding["sceneTransform"]["rotationDegrees"]
    scale = binding["sceneTransform"]["scale"]
    root.location = (float(translation[0]), float(translation[1]), float(translation[2]))
    root.rotation_euler = tuple(math.radians(float(v)) for v in rotation)
    root.scale = tuple(float(v) for v in scale)
    root["FeatureId"] = feature_id
    root["AssetId"] = manifest["assetId"]
    root["PlacementBindingHash"] = binding["bindingHash"]
    root["ScenePlacementAuthority"] = "canonical-scene"

    created = []
    for part in manifest["lods"]["lod0"]["meshParts"]:
        obj, triangles = _create_object(
            obj_path=_repo_path(part["path"]),
            name=part["name"],
            collection=collection,
            material_class=part.get("materialClass", "default"),
            custom_properties={
                "FeatureId": feature_id,
                "SourceFeatureId": manifest["sourceFeatureId"],
                "AssetId": manifest["assetId"],
                "ProductionStage": manifest["productionStage"],
                "LOD": "lod0",
                "StableMeshName": part["name"],
                "PlacementBindingHash": binding["bindingHash"],
                "ScenePlacementAuthority": "canonical-scene",
            },
        )
        obj.parent = root
        created.append({"name": obj.name, "triangleEquivalent": triangles})

    for part in manifest.get("collision", {}).get("meshParts", []):
        obj, triangles = _create_object(
            obj_path=_repo_path(part["path"]),
            name=part["name"],
            collection=collection,
            material_class="collision-proxy",
            custom_properties={
                "FeatureId": feature_id,
                "AssetId": manifest["assetId"],
                "LOD": "collision",
                "CollisionProxy": True,
                "PlacementBindingHash": binding["bindingHash"],
            },
        )
        obj.parent = root
        obj.hide_render = True
        obj.hide_set(True)
        created.append({"name": obj.name, "triangleEquivalent": triangles})

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))

    qa = {
        "status": "pass",
        "featureId": feature_id,
        "assetId": manifest["assetId"],
        "baseBlend": base_blend.as_posix(),
        "outputBlend": output.as_posix(),
        "hiddenGreyboxProxyCount": len(existing_proxy_objects),
        "rootTranslationLocalMeters": [float(v) for v in translation],
        "rootRotationDegrees": [float(v) for v in rotation],
        "rootScale": [float(v) for v in scale],
        "createdObjects": created,
        "placementBindingHash": binding["bindingHash"],
        "note": "LOD0 only is shown. Original matching greybox objects are hidden, not deleted.",
    }
    _write(output.with_suffix(".qa.json"), qa)
    return qa


def _args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-blend", type=Path, required=True)
    parser.add_argument("--asset-manifest", type=Path, required=True)
    parser.add_argument("--placement-binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = _args(argv)
    report = build_preview(args.base_blend, args.asset_manifest, args.placement_binding, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
