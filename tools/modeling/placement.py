from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import shape

from tools.geodata.transform import CoordinateTransform

from .geometry_v2 import project_wgs84_geometry_to_local_meters

UTM51 = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)


def _hash_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _feature_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("type") == "FeatureCollection":
        rows = snapshot.get("features", [])
        if len(rows) != 1:
            raise ValueError("placement snapshot FeatureCollection must contain exactly one feature")
        return rows[0]
    if "feature" in snapshot:
        return snapshot["feature"]
    return snapshot


def build_placement_binding(
    *,
    feature_snapshot: dict[str, Any],
    production_spec: dict[str, Any],
    asset_manifest: dict[str, Any],
    scene_object: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind model-local metres to the canonical scene coordinate contract.

    The production model is centered on the projected footprint centroid.  This
    binding makes that translation explicit so art can never silently move a
    building to fit a render or Studio scene.
    """

    feature = _feature_from_snapshot(feature_snapshot)
    source_id = production_spec.get("sourceFeatureId") or production_spec.get("featureId")
    if feature.get("id") != source_id:
        raise ValueError(f"feature snapshot id {feature.get('id')!r} does not match spec sourceFeatureId {source_id!r}")

    geometry = feature.get("geometry")
    if not geometry:
        raise ValueError("placement binding requires feature geometry")
    projected = project_wgs84_geometry_to_local_meters(geometry)
    origin_e, origin_n = projected["originUtm51"]

    transform = CoordinateTransform()
    translation_e = origin_e - transform.origin_e
    translation_n = origin_n - transform.origin_n
    scene_base = 0.0
    scene_feature_id = None
    scene_validation: dict[str, Any] = {"status": "not-checked", "errors": [], "maxPlanarErrorM": None}

    if scene_object is not None:
        scene_feature_id = scene_object.get("featureId")
        allowed_ids = {production_spec.get("proposedFeatureId"), production_spec.get("featureId"), source_id}
        if scene_feature_id not in allowed_ids:
            raise ValueError(f"scene object featureId {scene_feature_id!r} does not match production/source identity")
        placement = scene_object.get("placement") or {}
        scene_base = float(placement.get("relativeElevationM", placement.get("baseElevationM", 0.0)))

        # Compare source geometry after both independent transforms.  This is a
        # software transform check, not a claim about source survey accuracy.
        source_points_local: list[tuple[float, float]] = []
        model_points_local: list[tuple[float, float]] = []

        def collect_source(value: Any) -> None:
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
                lon, lat = float(value[0]), float(value[1])
                east, north, _ = transform.wgs84_to_local(lon, lat)
                source_points_local.append((east, north))
                return
            if isinstance(value, list):
                for child in value:
                    collect_source(child)

        def collect_model(value: Any) -> None:
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
                model_points_local.append((float(value[0]) + translation_e, float(value[1]) + translation_n))
                return
            if isinstance(value, list):
                for child in value:
                    collect_model(child)

        collect_source(geometry.get("coordinates"))
        collect_model(projected["coordinatesLocalMeters"])
        errors: list[str] = []
        if len(source_points_local) != len(model_points_local):
            errors.append("source/model point counts differ")
            max_error = None
        else:
            distances = [math.dist(a, b) for a, b in zip(source_points_local, model_points_local)]
            max_error = max(distances, default=0.0)
            if max_error > 1e-5:
                errors.append(f"model-local to scene-local planar round-trip error {max_error:.9f}m exceeds tolerance")
        scene_validation = {
            "status": "pass" if not errors else "fail",
            "errors": errors,
            "maxPlanarErrorM": round(max_error, 9) if max_error is not None else None,
        }

    binding = {
        "schemaVersion": "uplb-building-placement-binding-v0.1",
        "featureId": production_spec.get("proposedFeatureId") or production_spec.get("featureId"),
        "sourceFeatureId": source_id,
        "sceneFeatureId": scene_feature_id,
        "assetId": asset_manifest.get("assetId"),
        "modelSpace": {
            "units": "meters",
            "x": "east",
            "y": "north",
            "z": "up",
            "originPolicy": "projected-footprint-centroid",
            "originUtm51": [round(origin_e, 6), round(origin_n, 6)],
        },
        "sceneTransform": {
            "translationLocalMeters": [round(translation_e, 6), round(translation_n, 6), round(scene_base, 6)],
            "rotationDegrees": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "authority": "canonical-scene-placement",
        },
        "robloxTransformContract": {
            "metersPerStud": transform.config.meters_per_stud,
            "east": "+X",
            "up": "+Y",
            "north": "-Z",
            "translationStuds": [
                round(translation_e / transform.config.meters_per_stud, 6),
                round(scene_base / transform.config.meters_per_stud, 6),
                round(-translation_n / transform.config.meters_per_stud, 6),
            ],
        },
        "softwareTransformValidation": scene_validation,
        "sourceUncertaintySeparated": True,
    }
    binding["bindingHash"] = _hash_json(binding)
    return binding


def bind_file(
    *,
    feature_snapshot_path: Path,
    spec_path: Path,
    asset_manifest_path: Path,
    output_path: Path,
    scene_object: dict[str, Any] | None = None,
) -> dict[str, Any]:
    binding = build_placement_binding(
        feature_snapshot=json.loads(Path(feature_snapshot_path).read_text(encoding="utf-8")),
        production_spec=json.loads(Path(spec_path).read_text(encoding="utf-8")),
        asset_manifest=json.loads(Path(asset_manifest_path).read_text(encoding="utf-8")),
        scene_object=scene_object,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return binding
