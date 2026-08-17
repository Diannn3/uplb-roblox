from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _hash_payload(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_bindings(paths: Iterable[Path]) -> list[dict[str, Any]]:
    bindings = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    feature_ids = [row["featureId"] for row in bindings]
    if len(feature_ids) != len(set(feature_ids)):
        raise ValueError("duplicate production featureId bindings")
    asset_ids = [row["assetId"] for row in bindings]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("duplicate production assetId bindings")
    return bindings


def bind_production_assets(scene_spec: dict[str, Any], bindings: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Attach immutable production bindings without modifying source geometry.

    The canonical scene remains placement authority. This projection only adds
    an asset binding/transform consumed by Blender or Roblox asset handoff code.
    """

    result = json.loads(json.dumps(scene_spec, ensure_ascii=False, sort_keys=True))
    objects = result.get("objects", [])
    by_feature = {str(obj.get("featureId")): obj for obj in objects if obj.get("featureId")}
    by_candidate = {str(obj.get("candidateId")): obj for obj in objects if obj.get("candidateId")}
    attached: list[str] = []
    errors: list[str] = []

    for binding in bindings:
        feature_id = str(binding["featureId"])
        source_id = str(binding["sourceFeatureId"])
        target = by_feature.get(feature_id) or by_feature.get(source_id) or by_candidate.get(source_id)
        if not target:
            errors.append(f"no scene object matches production binding {feature_id} / {source_id}")
            continue
        if target.get("productionAsset"):
            errors.append(f"scene object already has production asset binding: {target.get('id')}")
            continue
        target["productionAsset"] = {
            "assetId": binding["assetId"],
            "featureId": feature_id,
            "sourceFeatureId": source_id,
            "modelSpace": binding["modelSpace"],
            "sceneTransform": binding["sceneTransform"],
            "robloxTransformContract": binding["robloxTransformContract"],
            "bindingHash": binding["bindingHash"],
            "placementAuthority": "canonical-scene",
        }
        attached.append(feature_id)

    metadata = result.setdefault("metadata", {})
    metadata["productionAssetBinding"] = {
        "status": "pass" if not errors else "fail",
        "attachedFeatureIds": sorted(attached),
        "errors": errors,
        "bindingCount": len(attached),
    }
    metadata["productionSceneHash"] = _hash_payload(result)
    if errors:
        raise ValueError("production scene binding failure: " + "; ".join(errors))
    return result


def bind_files(scene_spec_path: Path, binding_paths: Iterable[Path], output_path: Path) -> dict[str, Any]:
    scene = json.loads(Path(scene_spec_path).read_text(encoding="utf-8"))
    result = bind_production_assets(scene, load_bindings(binding_paths))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result
