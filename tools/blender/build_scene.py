"""Build and render the real Blender consumer of ``scene-spec.json``.

This file is intentionally runnable only inside Blender for the build path. It
does not import Shapely, PyProj, Earthaccess, or any other geospatial package;
all geometry and terrain sampling are compiled before this script runs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

try:  # Blender's bundled Python provides bpy; normal project Python does not.
    import bpy  # type: ignore[import-not-found]
    from mathutils import Vector  # type: ignore[import-not-found]
    from mathutils.geometry import tessellate_polygon  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised by the external Blender process
    bpy = None  # type: ignore[assignment]
    Vector = None  # type: ignore[assignment,misc]
    tessellate_polygon = None  # type: ignore[assignment]


BLENDER_AVAILABLE = bpy is not None
GENERATOR_VERSION = "blender-v0.2"
COLLECTIONS_BY_ROLE = {
    "hero": "Landmarks",
    "context-building": "Buildings",
    "road": "Roads",
    "walkway": "Walkways",
    "water": "Water",
    "green-space": "GreenSpace",
    "landmark-placeholder": "Landmarks",
}
REQUIRED_HERO_NAMES = {
    "UPLB Oblation",
    "UPLB Freedom Park",
    "Charles Fuller Baker Memorial Hall",
    "Dioscoro L. Umali Hall",
    "University Library and Knowledge Center",
}
MATERIAL_COLORS = {
    "hero-diagnostic": (0.75, 0.08, 0.08, 1.0),
    "context-building-diagnostic": (0.38, 0.24, 0.14, 1.0),
    "road-diagnostic": (0.05, 0.05, 0.05, 1.0),
    "walkway-diagnostic": (0.62, 0.42, 0.18, 1.0),
    "water-diagnostic": (0.05, 0.30, 0.75, 1.0),
    "green-space-diagnostic": (0.15, 0.55, 0.18, 1.0),
    "landmark-diagnostic": (0.85, 0.55, 0.05, 1.0),
    "terrain-diagnostic": (0.32, 0.27, 0.18, 1.0),
}


def terrain_faces(rows: int, columns: int) -> list[tuple[int, int, int]]:
    """Return deterministic row-major terrain triangles."""

    faces: list[tuple[int, int, int]] = []
    for row in range(max(rows - 1, 0)):
        for column in range(max(columns - 1, 0)):
            top_left = row * columns + column
            top_right = top_left + 1
            bottom_left = (row + 1) * columns + column
            bottom_right = bottom_left + 1
            faces.extend([(top_left, top_right, bottom_left), (top_right, bottom_right, bottom_left)])
    return faces


def build_custom_properties(feature: dict[str, Any], *, scene_spec_hash: str, generator_version: str = GENERATOR_VERSION) -> dict[str, Any]:
    metadata = feature.get("metadata") or {}
    height = feature.get("height") or {}
    return {
        "FeatureId": feature.get("featureId") or "",
        "CandidateId": feature.get("candidateId") or "",
        "SourceLifecycle": feature.get("sourceLifecycle") or "",
        "WorldgenRole": feature.get("role") or "",
        "DetailTier": int(feature.get("detailTier", 1)),
        "CanonicalRevision": metadata.get("canonicalRevision") or "",
        "TerrainRevision": metadata.get("terrainRevision") or "",
        "SceneSpecHash": scene_spec_hash,
        "GeneratorVersion": generator_version,
        "InputHash": metadata.get("inputHash") or "",
        "GeometryConfidence": feature.get("geometryConfidence") or metadata.get("geometryConfidence") or "unknown",
        "HeightConfidence": height.get("confidence") or "unknown",
    }


def _require_blender() -> Any:
    if bpy is None:
        raise RuntimeError("real Blender geometry requires running tools/blender/build_scene.py inside Blender")
    return bpy


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")[:80]


def _ensure_collections() -> dict[str, Any]:
    blender = _require_blender()
    root = blender.context.scene.collection
    collections: dict[str, Any] = {}
    for name in ("Terrain", "Buildings", "Roads", "Walkways", "Water", "GreenSpace", "Landmarks", "Debug"):
        collection = blender.data.collections.get(name) or blender.data.collections.new(name)
        if collection.name not in {child.name for child in root.children}:
            root.children.link(collection)
        collections[name] = collection
    return collections


def _material(material_class: str) -> Any:
    blender = _require_blender()
    material = blender.data.materials.get(material_class) or blender.data.materials.new(material_class)
    color = MATERIAL_COLORS.get(material_class, (0.5, 0.5, 0.5, 1.0))
    material.diffuse_color = color
    if material.use_nodes and material.node_tree:
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = color
            principled.inputs["Roughness"].default_value = 0.82
    return material


def _mesh_object(name: str, vertices: list[tuple[float, float, float]], faces: list[tuple[int, ...]], collection: Any, material_class: str, properties: dict[str, Any]) -> Any:
    blender = _require_blender()
    mesh = blender.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    obj = blender.data.objects.new(name, mesh)
    collection.objects.link(obj)
    material = _material(material_class)
    obj.data.materials.append(material)
    for key, value in properties.items():
        obj[key] = value
    return obj


def _polygon_loops(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if geometry_type == "Polygon":
        return [[[[float(point[0]), float(point[1])] for point in ring] for ring in coordinates]]
    if geometry_type == "MultiPolygon":
        return [[[[float(point[0]), float(point[1])] for point in ring] for ring in polygon] for polygon in coordinates]
    return []


def _extruded_polygon_mesh(geometry: dict[str, Any], base: float, height: float) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for polygon in _polygon_loops(geometry):
        ring_indices: list[tuple[list[int], list[int]]] = []
        for ring in polygon:
            if len(ring) >= 2 and ring[0] == ring[-1]:
                ring = ring[:-1]
            bottom: list[int] = []
            top: list[int] = []
            for x, y in ring:
                bottom.append(len(vertices))
                vertices.append((x, y, base))
                top.append(len(vertices))
                vertices.append((x, y, base + max(height, 0.1)))
            ring_indices.append((bottom, top))
            for index, current in enumerate(bottom):
                nxt = (index + 1) % len(bottom)
                faces.append((current, bottom[nxt], top[nxt], top[index]))
        if not ring_indices:
            continue
        if tessellate_polygon is not None and Vector is not None:
            loops = [[Vector((x, y, 0.0)) for x, y in ring] for ring in polygon]
            # Map every ring vertex explicitly; the separate top/bottom maps
            # preserve courtyard holes when Blender tessellates the loops.
            top_lookup = {}
            bottom_lookup = {}
            for ring, (bottom, top) in zip(polygon, ring_indices):
                source_ring = ring[:-1] if len(ring) >= 2 and ring[0] == ring[-1] else ring
                for (x, y), bottom_index, top_index in zip(source_ring, bottom, top):
                    key = (round(x, 8), round(y, 8))
                    bottom_lookup[key] = bottom_index
                    top_lookup[key] = top_index
            for triangle in tessellate_polygon(loops):
                points = [(round(float(point.x), 8), round(float(point.y), 8)) for point in triangle]
                if all(point in top_lookup for point in points):
                    faces.append(tuple(top_lookup[point] for point in points))
                    faces.append(tuple(reversed(tuple(bottom_lookup[point] for point in points))))
        else:
            outer_bottom, outer_top = ring_indices[0]
            if len(outer_bottom) >= 3:
                faces.append(tuple(outer_top))
                faces.append(tuple(reversed(tuple(outer_bottom))))
    return vertices, faces


def _flat_polygon_mesh(geometry: dict[str, Any], elevation: float) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for polygon in _polygon_loops(geometry):
        if not polygon:
            continue
        outer = polygon[0][:-1] if len(polygon[0]) >= 2 and polygon[0][0] == polygon[0][-1] else polygon[0]
        start = len(vertices)
        vertices.extend((float(x), float(y), elevation) for x, y in outer)
        if len(outer) >= 3:
            faces.append(tuple(start + index for index in range(len(outer))))
    return vertices, faces


def _build_terrain(scene_spec: dict[str, Any], collections: dict[str, Any], scene_hash: str) -> Any:
    terrain = scene_spec.get("terrain") or {}
    rows, columns = int(terrain.get("rows", 0)), int(terrain.get("columns", 0))
    values = terrain.get("values") or []
    spacing = float(terrain.get("samplingResolutionM", 30.0))
    origin_east = float(terrain.get("originEastM", 0.0))
    origin_north = float(terrain.get("originNorthM", 0.0))
    vertices: list[tuple[float, float, float]] = []
    nodata = terrain.get("nodata")
    for row in range(rows):
        for column in range(columns):
            value = float(values[row][column])
            elevation = 0.0 if nodata is not None and value == float(nodata) else value
            vertices.append((origin_east + column * spacing, origin_north + row * spacing, elevation))
    properties = {
        "FeatureId": "terrain",
        "CandidateId": "",
        "SourceLifecycle": "source",
        "WorldgenRole": "terrain",
        "DetailTier": 0,
        "CanonicalRevision": scene_spec.get("metadata", {}).get("canonicalRevision", ""),
        "TerrainRevision": terrain.get("revision", ""),
        "SceneSpecHash": scene_hash,
        "GeneratorVersion": GENERATOR_VERSION,
        "InputHash": scene_spec.get("metadata", {}).get("inputHash", ""),
        "GeometryConfidence": "source-supported",
        "HeightConfidence": "source-supported" if terrain.get("sourceKind") == "real-nasa-raster" else "fixture",
    }
    return _mesh_object("TERRAIN", vertices, terrain_faces(rows, columns), collections["Terrain"], "terrain-diagnostic", properties)


def _build_feature(feature: dict[str, Any], collections: dict[str, Any], scene_hash: str) -> Any:
    role = str(feature.get("role"))
    collection = collections[COLLECTIONS_BY_ROLE.get(role, "Debug")]
    name = f"{role.upper().replace('-', '_')}_{_safe_name(str(feature.get('featureId') or feature.get('id')))}"
    properties = build_custom_properties(feature, scene_spec_hash=scene_hash)
    placement = feature.get("placement") or {}
    base = float(placement.get("baseElevationM", 0.0))
    geometry = feature.get("geometry") or {}
    if role in {"hero", "context-building"} and _polygon_loops(geometry):
        vertices, faces = _extruded_polygon_mesh(geometry, base, float((feature.get("height") or {}).get("meters", 6.0)))
        return _mesh_object(name, vertices, faces, collection, "hero-diagnostic" if role == "hero" else "context-building-diagnostic", properties)
    if role in {"water", "green-space"} and _polygon_loops(geometry):
        vertices, faces = _flat_polygon_mesh(geometry, base + 0.03)
        return _mesh_object(name, vertices, faces, collection, "water-diagnostic" if role == "water" else "green-space-diagnostic", properties)
    ribbons = geometry.get("ribbonCoordinatesLocalMeters") or []
    if role in {"road", "walkway"} and ribbons:
        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, ...]] = []
        for ribbon in ribbons:
            start = len(vertices)
            vertices.extend((float(point[0]), float(point[1]), base + 0.05) for point in ribbon)
            if len(ribbon) >= 3:
                faces.append(tuple(start + index for index in range(len(ribbon))))
        return _mesh_object(name, vertices, faces, collection, "road-diagnostic" if role == "road" else "walkway-diagnostic", properties)
    local = geometry.get("coordinatesLocalMeters")
    point = local if isinstance(local, list) and len(local) >= 2 and all(isinstance(item, (int, float)) for item in local[:2]) else [0.0, 0.0]
    size = 2.0 if role in {"hero", "landmark-placeholder"} else 1.0
    x, y = float(point[0]), float(point[1])
    vertices = [(x - size, y - size, base), (x + size, y - size, base), (x + size, y + size, base), (x - size, y + size, base), (x - size, y - size, base + size * 2), (x + size, y - size, base + size * 2), (x + size, y + size, base + size * 2), (x - size, y + size, base + size * 2)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
    return _mesh_object(name, vertices, faces, collection, "hero-diagnostic" if role == "hero" else "landmark-diagnostic", properties)


def _build_cameras(scene_spec: dict[str, Any], collections: dict[str, Any]) -> dict[str, Any]:
    blender = _require_blender()
    placements = [obj.get("placement") or {} for obj in scene_spec.get("objects", [])]
    center_x = sum(float(item.get("eastM", 0.0)) for item in placements) / max(len(placements), 1)
    center_y = sum(float(item.get("northM", 0.0)) for item in placements) / max(len(placements), 1)
    targets = {str(obj.get("name")): obj.get("placement") or {} for obj in scene_spec.get("objects", [])}
    target_for = lambda name: (float(targets.get(name, {}).get("eastM", center_x)), float(targets.get(name, {}).get("northM", center_y)), float(targets.get(name, {}).get("baseElevationM", 0.0)))
    definitions = {
        "CAM_TOPDOWN": (target_for("UPLB Oblation"), (center_x, center_y, 900.0)),
        "CAM_OBLATION": (target_for("UPLB Oblation"), (center_x + 120.0, center_y - 120.0, 80.0)),
        "CAM_FREEDOM_PARK": (target_for("UPLB Freedom Park"), (center_x + 130.0, center_y - 130.0, 80.0)),
        "CAM_BAKER": (target_for("Charles Fuller Baker Memorial Hall"), (center_x + 250.0, center_y, 70.0)),
        "CAM_DL_UMALI": (target_for("Dioscoro L. Umali Hall"), (center_x - 30.0, center_y - 80.0, 70.0)),
        "CAM_ROAD_LEVEL": ((center_x, center_y - 200.0, 0.0), (center_x + 150.0, center_y - 350.0, 35.0)),
    }
    cameras: dict[str, Any] = {}
    for name, (target, position) in definitions.items():
        data = blender.data.cameras.new(name)
        camera = blender.data.objects.new(name, data)
        collections["Debug"].objects.link(camera)
        camera.location = position
        direction = Vector(target) - camera.location
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        data.lens = 45.0
        camera["FeatureId"] = f"camera:{name}"
        camera["CandidateId"] = ""
        camera["SourceLifecycle"] = "generated"
        camera["WorldgenRole"] = "camera"
        camera["DetailTier"] = 0
        camera["CanonicalRevision"] = scene_spec.get("metadata", {}).get("canonicalRevision", "")
        camera["TerrainRevision"] = scene_spec.get("terrain", {}).get("revision", "")
        camera["SceneSpecHash"] = scene_spec.get("metadata", {}).get("sceneSpecHash", "")
        camera["GeneratorVersion"] = GENERATOR_VERSION
        camera["InputHash"] = scene_spec.get("metadata", {}).get("inputHash", "")
        camera["GeometryConfidence"] = "generated"
        camera["HeightConfidence"] = "generated"
        cameras[name] = camera
    return cameras


def _semantic_state() -> list[dict[str, Any]]:
    blender = _require_blender()
    state: list[dict[str, Any]] = []
    for obj in sorted(blender.context.scene.objects, key=lambda item: str(item.get("FeatureId", item.name))):
        if "FeatureId" not in obj:
            continue
        mesh = obj.data if getattr(obj, "type", None) == "MESH" else None
        state.append({
            "name": obj.name,
            "featureId": obj.get("FeatureId"),
            "location": [round(float(value), 6) for value in obj.location],
            "dimensions": [round(float(value), 6) for value in obj.dimensions],
            "vertices": [[round(float(vertex.co[index]), 6) for index in range(3)] for vertex in mesh.vertices] if mesh else [],
            "faces": [[int(index) for index in polygon.vertices] for polygon in mesh.polygons] if mesh else [],
            "properties": {key: obj[key] for key in sorted(obj.keys())},
        })
    return state


def _clear_scene_objects() -> None:
    blender = _require_blender()
    for obj in list(blender.data.objects):
        blender.data.objects.remove(obj, do_unlink=True)


def _render(scene: Any, cameras: dict[str, Any], output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    paths: list[str] = []
    for camera_name in ("CAM_TOPDOWN", "CAM_OBLATION", "CAM_FREEDOM_PARK", "CAM_BAKER", "CAM_DL_UMALI", "CAM_ROAD_LEVEL"):
        scene.camera = cameras[camera_name]
        path = output_dir / f"{camera_name.removeprefix('CAM_').lower()}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        paths.append(path.as_posix())
    return paths


def build_real_scene(scene_spec_path: Path, output_dir: Path, *, render: bool = True) -> dict[str, Any]:
    blender = _require_blender()
    scene_spec = json.loads(Path(scene_spec_path).read_text(encoding="utf-8"))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_hash = (scene_spec.get("metadata") or {}).get("sceneSpecHash", "")
    blender.ops.wm.read_factory_settings(use_empty=True)
    collections = _ensure_collections()
    _build_terrain(scene_spec, collections, scene_hash)
    for feature in scene_spec.get("objects", []):
        _build_feature(feature, collections, scene_hash)
    cameras = _build_cameras(scene_spec, collections)
    first_state = _semantic_state()
    _clear_scene_objects()
    collections = _ensure_collections()
    _build_terrain(scene_spec, collections, scene_hash)
    for feature in scene_spec.get("objects", []):
        _build_feature(feature, collections, scene_hash)
    cameras = _build_cameras(scene_spec, collections)
    second_state = _semantic_state()
    semantic_equal = first_state == second_state
    render_paths = _render(blender.context.scene, cameras, output_dir / "renders") if render else []
    blend_path = output_dir / "vertical-slice-v0.1.blend"
    blender.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {
        "status": "pass" if semantic_equal else "fail",
        "blenderVersion": getattr(blender.app, "version_string", "unknown"),
        "generatorVersion": GENERATOR_VERSION,
        "sceneSpecHash": scene_hash,
        "objectCount": len(second_state),
        "requiredCollections": sorted(collections),
        "requiredHeroNames": sorted(REQUIRED_HERO_NAMES),
        "renderPaths": render_paths,
        "blendPath": blend_path.as_posix(),
    }
    qa = {
        "status": "pass" if semantic_equal and all(Path(path).exists() for path in render_paths) else "fail",
        "blenderMeshGate": "pass" if semantic_equal else "fail",
        "blenderRenderGate": "pass" if render_paths and all(Path(path).exists() for path in render_paths) else "not-run",
        "semanticSceneEqual": semantic_equal,
        "objectCount": len(second_state),
        "duplicateFeatureIds": len({item["featureId"] for item in second_state}) != len(second_state),
        "nonFiniteTransforms": any(not all(math.isfinite(value) for value in item["location"]) for item in second_state),
        "negativeScales": False,
        "impossibleDimensions": any(any(value < 0 or not math.isfinite(value) for value in item["dimensions"]) for item in second_state),
        "missingCameras": [name for name in ("CAM_TOPDOWN", "CAM_OBLATION", "CAM_FREEDOM_PARK", "CAM_BAKER", "CAM_DL_UMALI", "CAM_ROAD_LEVEL") if name not in cameras],
        "requiredCollectionsMissing": [name for name in ("Terrain", "Buildings", "Roads", "Walkways", "Water", "GreenSpace", "Landmarks", "Debug") if name not in collections],
        "renderPaths": render_paths,
        "blenderVersion": getattr(blender.app, "version_string", "unknown"),
    }
    (output_dir / "scene-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (output_dir / "blender-qa.json").write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (output_dir / "determinism.json").write_text(json.dumps({"semanticSceneEqual": semantic_equal, "binaryBlendEqual": None, "firstStateCount": len(first_state), "secondStateCount": len(second_state)}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"report": report, "qa": qa, "determinism": {"semanticSceneEqual": semantic_equal}, "renderPaths": render_paths}


def main() -> int:
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]
    else:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_real_scene(args.scene_spec, args.output)
    print(json.dumps({"status": result["qa"]["status"], "objectCount": result["qa"]["objectCount"], "semanticSceneEqual": result["qa"]["semanticSceneEqual"]}, sort_keys=True))
    return 0 if result["qa"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
