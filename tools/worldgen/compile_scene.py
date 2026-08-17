"""Compile canonical/context slice data and terrain into one scene specification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from shapely.geometry import shape

from tools.blender.buildings import resolve_height
from tools.blender.config import GreyboxConfig
from tools.blender.environment import environment_dimensions
from tools.blender.roads import resolve_width
from tools.blender.walkways import resolve_walkway_width
from tools.geodata.io import read_json, sha256, write_json
from tools.geodata.transform import CoordinateTransform
from tools.terrain.sample import HeightField


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SLICE = ROOT / "data" / "vertical-slices" / "v0.1"
DEFAULT_TERRAIN = ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json"
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "worldgen-v0.1"
SCENE_REVISION = "worldgen-v0.1"


def _hash_payload(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _local_point(transform: CoordinateTransform, coordinate: Iterable[float]) -> list[float]:
    east, north, _ = transform.wgs84_to_local(float(coordinate[0]), float(coordinate[1]))
    return [round(east, 6), round(north, 6)]


def _local_coordinates(geometry: dict[str, Any], transform: CoordinateTransform) -> Any:
    geometry_type = str(geometry.get("type"))
    coordinates = geometry.get("coordinates")
    if geometry_type == "GeometryCollection":
        return [_local_coordinates(item, transform) for item in geometry.get("geometries", [])]
    if geometry_type.startswith("Multi"):
        return [_local_coordinates({"type": geometry_type.removeprefix("Multi"), "coordinates": child}, transform) for child in coordinates or []]
    if geometry_type == "Point":
        return _local_point(transform, coordinates)
    if geometry_type in {"LineString", "MultiPoint"}:
        return [_local_point(transform, coordinate) for coordinate in coordinates or []]
    if geometry_type == "Polygon":
        return [[_local_point(transform, coordinate) for coordinate in ring] for ring in coordinates or []]
    raise ValueError(f"unsupported scene geometry type: {geometry_type}")


def _flatten_points(value: Any) -> list[list[float]]:
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        return [[float(value[0]), float(value[1])]]
    points: list[list[float]] = []
    for child in value or []:
        points.extend(_flatten_points(child))
    return points


def _ribbon(points: list[list[float]], width_m: float) -> list[list[list[float]]]:
    if len(points) < 2:
        return []
    half = max(float(width_m), 0.01) / 2.0
    ribbons: list[list[list[float]]] = []
    for first, second in zip(points, points[1:]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue
        nx, ny = -dy / length * half, dx / length * half
        ribbons.append(
            [
                [round(first[0] + nx, 6), round(first[1] + ny, 6)],
                [round(second[0] + nx, 6), round(second[1] + ny, 6)],
                [round(second[0] - nx, 6), round(second[1] - ny, 6)],
                [round(first[0] - nx, 6), round(first[1] - ny, 6)],
                [round(first[0] + nx, 6), round(first[1] + ny, 6)],
            ]
        )
    return ribbons


def _material(role: str) -> str:
    return {
        "hero": "hero-diagnostic",
        "context-building": "context-building-diagnostic",
        "road": "road-diagnostic",
        "walkway": "walkway-diagnostic",
        "water": "water-diagnostic",
        "green-space": "green-space-diagnostic",
        "landmark-placeholder": "landmark-diagnostic",
    }.get(role, "unclassified-diagnostic")


def _terrain_metadata(terrain_path: Path, field: HeightField) -> dict[str, Any]:
    manifest_path = terrain_path.parent / "terrain-manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    return {
        "product": field.product,
        "sourceKind": field.source_kind,
        "sourceHash": manifest.get("sourceHash"),
        "sourceCRS": manifest.get("horizontalCRS", "EPSG:4326"),
        "localCRS": "EPSG:32651",
        "horizontalDatum": manifest.get("horizontalDatum", "WGS84"),
        "verticalDatum": manifest.get("verticalDatum", "EGM96"),
        "nativeResolutionM": manifest.get("resolutionM", 30),
        "samplingResolutionM": field.spacing_m,
        "originEastM": field.origin_east_m,
        "originNorthM": field.origin_north_m,
        "rows": field.rows,
        "columns": field.columns,
        "nodata": field.nodata,
        "values": [list(row) for row in field.values],
        "interpolationPolicy": "bilinear at HGT sample; local grid uses inverse EPSG:32651 to WGS84",
    }


def _object(feature: dict[str, Any], transform: CoordinateTransform, field: HeightField, config: GreyboxConfig, selection: dict[str, Any], terrain: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") or {}
    role = str(props.get("worldgenRole"))
    geometry = feature.get("geometry")
    if not geometry:
        raise ValueError(f"feature has no geometry: {feature.get('id')}")
    local_geometry = _local_coordinates(geometry, transform)
    representative = shape(geometry).representative_point()
    east, north, _ = transform.wgs84_to_local(float(representative.x), float(representative.y))
    try:
        base = field.ground_height(east, north)
        terrain_sampling = "sampled"
    except ValueError:
        base = 0.0
        terrain_sampling = "outside-fixture-extent" if field.source_kind == "synthetic-fixture" else "missing"
    height = 0.0
    height_method = "not-applicable"
    height_confidence = "unknown"
    width = 0.0
    width_method = "not-applicable"
    width_confidence = "unknown"
    if role in {"hero", "context-building"}:
        height, height_method, height_confidence = resolve_height(props, config)
    elif role == "road":
        width, width_method, width_confidence = resolve_width(props, config)
    elif role == "walkway":
        width, width_method, width_confidence = resolve_walkway_width(props, config)
    elif role in {"water", "green-space", "landmark-placeholder"}:
        width, width_method = environment_dimensions(props)
        width_confidence = "placeholder"
    flat = _flatten_points(local_geometry)
    ribbons = _ribbon(flat, width) if role in {"road", "walkway"} else []
    input_hash = _hash_payload(feature)
    return {
        "id": f"scene:{feature.get('id')}",
        "featureId": props.get("featureId") or feature.get("id"),
        "candidateId": props.get("candidateId"),
        "sourceLifecycle": props.get("sourceLifecycle"),
        "role": role,
        "name": props.get("name"),
        "detailTier": props.get("detailTier", 1),
        "geometryConfidence": props.get("geometryConfidence", "unknown"),
        "geometry": {
            "type": geometry.get("type"),
            "coordinatesLocalMeters": local_geometry,
            "ribbonCoordinatesLocalMeters": ribbons,
        },
        "placement": {"eastM": round(east, 6), "northM": round(north, 6), "baseElevationM": round(base, 6), "terrainSampling": terrain_sampling},
        "height": {"meters": round(max(height, 0.0), 6), "method": height_method, "confidence": height_confidence},
        "width": {"meters": round(max(width, 0.0), 6), "method": width_method, "confidence": width_confidence},
        "materialClass": _material(role),
        "metadata": {
            "canonicalRevision": selection.get("canonicalRevision"),
            "terrainRevision": terrain.get("revision", "terrain-v0.1-fixture"),
            "inputHash": input_hash,
            "sourceGeometryHash": props.get("sourceGeometryHash"),
            "verificationStatus": props.get("verificationStatus"),
        },
    }


def validate_scene_spec(scene_spec: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    objects = scene_spec.get("objects", [])
    ids = [obj.get("id") for obj in objects]
    if len(ids) != len(set(ids)):
        errors.append("duplicate scene object IDs")
    for obj in objects:
        placement = obj.get("placement") or {}
        values = [placement.get(key) for key in ("eastM", "northM", "baseElevationM")]
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            errors.append(f"non-finite placement: {obj.get('id')}")
        if abs(float(placement.get("eastM", 0))) > 10_000 or abs(float(placement.get("northM", 0))) > 10_000:
            errors.append(f"absurd placement: {obj.get('id')}")
        if obj.get("placement", {}).get("terrainSampling") == "outside-fixture-extent":
            warnings.append(f"fixture terrain does not cover {obj.get('id')}")
    if scene_spec.get("terrain", {}).get("sourceKind") != "real-nasa-raster":
        warnings.append("real terrain gate is blocked because scene spec uses a fixture")
    return {"status": "pass" if not errors else "fail", "errors": errors, "warnings": warnings, "objectCount": len(objects)}


def compile_scene(
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    slice_dir: Path = DEFAULT_SLICE,
    terrain_path: Path = DEFAULT_TERRAIN,
    allow_fixture: bool = False,
) -> dict[str, Any]:
    features_payload = read_json(Path(slice_dir) / "features.geojson")
    selection = read_json(Path(slice_dir) / "selection.json")
    terrain_path = Path(terrain_path)
    field = HeightField.read(terrain_path)
    if field.source_kind != "real-nasa-raster" and not allow_fixture:
        raise RuntimeError("scene compilation requires selected real NASA terrain; pass allow_fixture=True only for tests")
    transform = CoordinateTransform()
    config = GreyboxConfig()
    terrain = _terrain_metadata(terrain_path, field)
    terrain["revision"] = "terrain-v0.2-real" if field.source_kind == "real-nasa-raster" else "terrain-v0.1-fixture"
    objects = sorted((_object(feature, transform, field, config, selection, terrain) for feature in features_payload.get("features", [])), key=lambda item: item["id"])
    input_manifest = {
        "sceneRevision": SCENE_REVISION,
        "sliceVersion": selection.get("sliceVersion"),
        "sliceFeaturesHash": f"sha256:{sha256(Path(slice_dir) / 'features.geojson')}",
        "selectionHash": f"sha256:{sha256(Path(slice_dir) / 'selection.json')}",
        "bindingsHash": f"sha256:{sha256(Path(slice_dir) / 'canonical-bindings.json')}",
        "terrainHash": f"sha256:{sha256(terrain_path)}",
        "terrainSourceHash": terrain.get("sourceHash"),
    }
    scene_spec: dict[str, Any] = {
        "sceneRevision": SCENE_REVISION,
        "status": "ready" if field.source_kind == "real-nasa-raster" else "blocked-fixture-terrain",
        "coordinateContract": {"units": "local metres", "blender": {"x": "east", "y": "north", "z": "elevation"}, "roblox": {"east": "+X", "up": "+Y", "north": "-Z", "metersPerStud": 0.28}},
        "terrain": terrain,
        "objects": objects,
        "metadata": {"canonicalRevision": selection.get("canonicalRevision"), "candidateSourceHash": selection.get("candidateSourceHash"), "approvedReviewHash": selection.get("approvedReviewHash"), "inputHash": _hash_payload(input_manifest)},
    }
    scene_spec["metadata"]["sceneSpecHash"] = _hash_payload(scene_spec)
    validation = validate_scene_spec(scene_spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "scene-spec.json", scene_spec)
    write_json(output_dir / "scene-validation.json", validation)
    write_json(output_dir / "input-manifest.json", input_manifest)
    return {"sceneSpec": scene_spec, "sceneValidation": validation, "inputManifest": input_manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE)
    parser.add_argument("--terrain", type=Path, default=DEFAULT_TERRAIN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args()
    result = compile_scene(args.output, slice_dir=args.slice, terrain_path=args.terrain, allow_fixture=args.allow_fixture)
    print(json.dumps({"status": result["sceneSpec"]["status"], "objectCount": len(result["sceneSpec"]["objects"]), "sceneSpecHash": result["sceneSpec"]["metadata"]["sceneSpecHash"]}, indent=2, sort_keys=True))
    return 0 if result["sceneValidation"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
