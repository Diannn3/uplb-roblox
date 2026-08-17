"""Compile canonical/context slice data and terrain into one scene specification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
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


def _densify(points: list[list[float]], maximum_spacing_m: float) -> list[list[float]]:
    """Subdivide long source segments before terrain sampling."""

    if len(points) < 2:
        return points
    result: list[list[float]] = [points[0]]
    for first, second in zip(points, points[1:]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        steps = max(1, int(math.ceil(length / max(maximum_spacing_m, 0.01))))
        for step in range(1, steps + 1):
            fraction = step / steps
            result.append([first[0] + dx * fraction, first[1] + dy * fraction])
    return result


def _sample_elevation(field: HeightField, east: float, north: float, world_base: float, *, allow_fixture_outside: bool) -> tuple[float, str]:
    try:
        return field.ground_height(east, north), "sampled"
    except ValueError:
        if allow_fixture_outside and field.source_kind == "synthetic-fixture":
            return world_base, "outside-fixture-extent"
        raise


def _terrain_ribbon(
    points: list[list[float]],
    width_m: float,
    field: HeightField,
    world_base: float,
    *,
    sample_spacing_m: float,
    allow_fixture_outside: bool,
) -> tuple[list[list[list[float]]], list[list[list[float]]], list[list[float]], str]:
    """Build 2D and terrain-following 3D ribbon rings."""

    densified = _densify(points, sample_spacing_m)
    if len(densified) < 2:
        return [], [], [], "not-sampled"
    half = max(float(width_m), 0.01) / 2.0
    left: list[list[float]] = []
    right: list[list[float]] = []
    centerline: list[list[float]] = []
    statuses: list[str] = []
    for index, point in enumerate(densified):
        before = densified[max(index - 1, 0)]
        after = densified[min(index + 1, len(densified) - 1)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            nx, ny = 0.0, 1.0
        else:
            nx, ny = -dy / length, dx / length
        left_point = [point[0] + nx * half, point[1] + ny * half]
        right_point = [point[0] - nx * half, point[1] - ny * half]
        left_elevation, left_status = _sample_elevation(field, left_point[0], left_point[1], world_base, allow_fixture_outside=allow_fixture_outside)
        right_elevation, right_status = _sample_elevation(field, right_point[0], right_point[1], world_base, allow_fixture_outside=allow_fixture_outside)
        center_elevation, center_status = _sample_elevation(field, point[0], point[1], world_base, allow_fixture_outside=allow_fixture_outside)
        statuses.extend((left_status, right_status, center_status))
        left.append([round(left_point[0], 6), round(left_point[1], 6), round(left_elevation - world_base, 6)])
        right.append([round(right_point[0], 6), round(right_point[1], 6), round(right_elevation - world_base, 6)])
        centerline.append([round(point[0], 6), round(point[1], 6), round(center_elevation - world_base, 6)])
    rings_3d: list[list[list[float]]] = []
    rings_2d: list[list[list[float]]] = []
    for index in range(len(densified) - 1):
        ring_3d = [left[index], left[index + 1], right[index + 1], right[index], left[index]]
        rings_3d.append(ring_3d)
        rings_2d.append([[point[0], point[1]] for point in ring_3d])
    status = "sampled-per-vertex" if statuses and all(item == "sampled" for item in statuses) else "fixture-outside-extent"
    return rings_2d, rings_3d, centerline, status


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
    world_base = field.world_base_elevation_m
    if world_base is None:
        world_base = math.floor(field.min_elevation_m - 2.0)
    absolute_values = [list(row) for row in field.values]
    relative_values = [[round(float(value) - world_base, 6) for value in row] for row in field.values]
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
        "values": relative_values,
        "absoluteValues": absolute_values,
        "absoluteMinElevationM": field.min_elevation_m,
        "absoluteMaxElevationM": field.max_elevation_m,
        "relativeMinElevationM": field.min_elevation_m - world_base,
        "relativeMaxElevationM": field.max_elevation_m - world_base,
        "worldBaseElevationM": world_base,
        "verticalReference": {
            "sourceDatum": "EGM96",
            "worldBaseElevationM": world_base,
            "policy": field.vertical_reference_policy,
            "elevationSemantics": "values-relative; absoluteValues-retained-for-provenance",
        },
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
    world_base = float(terrain.get("worldBaseElevationM", 0.0))
    allow_fixture_outside = field.source_kind == "synthetic-fixture"
    flat = _flatten_points(local_geometry)
    unique_flat: list[list[float]] = []
    seen_points: set[tuple[float, float]] = set()
    for point in flat:
        key = (round(float(point[0]), 6), round(float(point[1]), 6))
        if key not in seen_points:
            seen_points.add(key)
            unique_flat.append([float(point[0]), float(point[1])])
    sample_points = unique_flat[:128] or [[east, north]]
    elevation_samples: list[float] = []
    sample_statuses: list[str] = []
    for point in sample_points:
        elevation, status = _sample_elevation(field, point[0], point[1], world_base, allow_fixture_outside=allow_fixture_outside)
        elevation_samples.append(elevation)
        sample_statuses.append(status)
    base = statistics.median(elevation_samples)
    terrain_sampling = "sampled" if all(status == "sampled" for status in sample_statuses) else "outside-fixture-extent"
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
    ribbons: list[list[list[float]]] = []
    ribbons_3d: list[list[list[float]]] = []
    centerline_3d: list[list[float]] = []
    if role in {"road", "walkway"}:
        ribbons, ribbons_3d, centerline_3d, ribbon_sampling = _terrain_ribbon(
            flat,
            width,
            field,
            world_base,
            sample_spacing_m=config.terrain_sample_spacing_m,
            allow_fixture_outside=allow_fixture_outside,
        )
        terrain_sampling = ribbon_sampling
    relative_base = base - world_base
    foundation = None
    if role in {"hero", "context-building"}:
        foundation = {
            "method": "median-footprint-terrain-sample",
            "minGroundElevationM": round(min(elevation_samples), 6),
            "maxGroundElevationM": round(max(elevation_samples), 6),
            "medianGroundElevationM": round(base, 6),
            "baseElevationM": round(relative_base, 6),
        }
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
            "ribbonCoordinatesLocalMeters3D": ribbons_3d,
            "centerlineCoordinatesLocalMeters3D": centerline_3d,
        },
        "placement": {
            "eastM": round(east, 6),
            "northM": round(north, 6),
            "absoluteElevationM": round(base, 6),
            "relativeElevationM": round(relative_base, 6),
            # Compatibility alias for the current Blender consumer; all
            # consumers now interpret this as relative-to-world-base metres.
            "baseElevationM": round(relative_base, 6),
            "terrainSampling": terrain_sampling,
        },
        "foundation": foundation,
        "height": {"meters": round(max(height, 0.0), 6), "method": height_method, "confidence": height_confidence},
        "width": {"meters": round(max(width, 0.0), 6), "method": width_method, "confidence": width_confidence},
        "materialClass": _material(role),
        "metadata": {
            "canonicalRevision": selection.get("canonicalRevision"),
            "terrainRevision": terrain.get("revision", "terrain-v0.1-fixture"),
            "inputHash": input_hash,
            "sourceGeometryHash": props.get("sourceGeometryHash"),
            "verificationStatus": props.get("verificationStatus"),
            "terrainSamplingMethod": "bilinear-heightfield-per-vertex" if role in {"road", "walkway"} else "bilinear-heightfield-representative-and-footprint",
            "terrainSampleSpacingM": config.terrain_sample_spacing_m if role in {"road", "walkway"} else None,
        },
    }


def validate_scene_spec(scene_spec: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    objects = scene_spec.get("objects", [])
    ids = [obj.get("id") for obj in objects]
    if len(ids) != len(set(ids)):
        errors.append("duplicate scene object IDs")
    feature_ids = [obj.get("featureId") for obj in objects if obj.get("featureId")]
    if len(feature_ids) != len(set(feature_ids)):
        errors.append("duplicate scene FeatureIds")
    required_heroes = {
        "UPLB Oblation",
        "UPLB Freedom Park",
        "Charles Fuller Baker Memorial Hall",
        "Dioscoro L. Umali Hall",
        "University Library and Knowledge Center",
    }
    missing_heroes = sorted(required_heroes - {str(obj.get("name")) for obj in objects if obj.get("role") == "hero"})
    if missing_heroes:
        errors.append("missing required heroes: " + ", ".join(missing_heroes))
    terrain = scene_spec.get("terrain") or {}
    world_base = terrain.get("worldBaseElevationM")
    if not isinstance(world_base, (int, float)) or not math.isfinite(float(world_base)):
        errors.append("terrain vertical reference is missing worldBaseElevationM")
    rows, columns = int(terrain.get("rows", 0)), int(terrain.get("columns", 0))
    spacing = float(terrain.get("samplingResolutionM", 0.0) or 0.0)
    origin_east, origin_north = float(terrain.get("originEastM", 0.0)), float(terrain.get("originNorthM", 0.0))
    terrain_bounds = (origin_east, origin_north, origin_east + max(columns - 1, 0) * spacing, origin_north + max(rows - 1, 0) * spacing)

    def points(value: Any) -> Iterable[tuple[float, float]]:
        if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            yield float(value[0]), float(value[1])
            return
        for child in value or []:
            yield from points(child)

    for obj in objects:
        placement = obj.get("placement") or {}
        values = [placement.get(key) for key in ("eastM", "northM", "baseElevationM", "absoluteElevationM", "relativeElevationM")]
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            errors.append(f"non-finite placement: {obj.get('id')}")
        if abs(float(placement.get("eastM", 0))) > 10_000 or abs(float(placement.get("northM", 0))) > 10_000:
            errors.append(f"absurd placement: {obj.get('id')}")
        if obj.get("placement", {}).get("terrainSampling") == "outside-fixture-extent":
            warnings.append(f"fixture terrain does not cover {obj.get('id')}")
        geometry = obj.get("geometry") or {}
        geometry_points = list(points(geometry.get("coordinatesLocalMeters"))) + list(points(geometry.get("ribbonCoordinatesLocalMeters3D")))
        outside = [point for point in geometry_points if not (terrain_bounds[0] <= point[0] <= terrain_bounds[2] and terrain_bounds[1] <= point[1] <= terrain_bounds[3])]
        if outside:
            if terrain.get("sourceKind") == "real-nasa-raster":
                errors.append(f"object outside terrain coverage: {obj.get('id')}")
            else:
                warnings.append(f"fixture terrain does not cover geometry for {obj.get('id')}")
    if terrain.get("sourceKind") != "real-nasa-raster":
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
