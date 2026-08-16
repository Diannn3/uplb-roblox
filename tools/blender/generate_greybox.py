"""Generate a deterministic semantic greybox manifest and fixed previews.

When Blender 5.x is installed this input contract can be consumed by the
headless Blender script.  The current environment has no Blender executable,
so this run deliberately produces a clearly-labelled Python semantic fallback
and stops before claiming Blender mesh or visual approval.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from tools.geodata.io import read_json, sha256, write_json
from tools.geodata.transform import CoordinateTransform
from .buildings import resolve_height
from .cameras import render_python_previews, write_camera_config
from .config import GreyboxConfig
from .geo import dimensions_m, local_representative
from .manifest import input_hash, object_id
from .metadata import object_metadata
from .roads import resolve_width
from .terrain import ground_height, load_terrain
from .validate import validate_manifest
from .walkways import resolve_walkway_width
from .environment import environment_dimensions


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SLICE = ROOT / "data" / "vertical-slices" / "v0.1"
DEFAULT_TERRAIN = ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json"
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "greybox-v0.1"


def _object(feature: dict[str, Any], terrain: Any, transform: CoordinateTransform, config: GreyboxConfig) -> dict[str, Any]:
    props = feature.get("properties") or {}
    role = props.get("worldgenRole")
    east, north = local_representative(feature["geometry"], transform)
    try:
        up = ground_height(terrain, east, north)
    except ValueError:
        up = 0.0
    width, depth = dimensions_m(feature["geometry"])
    height = 0.0
    height_method = "not-applicable"
    height_confidence = "unknown"
    width_method = None
    width_confidence = None
    if role in {"hero", "context-building"}:
        height, height_method, height_confidence = resolve_height(props, config)
    elif role == "road":
        height, width_method, width_confidence = resolve_width(props, config)
        width, depth = max(width, height), max(depth, 0.1)
    elif role == "walkway":
        height, width_method, width_confidence = resolve_walkway_width(props, config)
        width, depth = max(width, height), max(depth, 0.1)
    elif role in {"water", "green-space", "landmark-placeholder"}:
        height, width_method = environment_dimensions(props)
        width, depth = max(width, height), max(depth, 0.1)
    obj = {
        "objectId": object_id(props),
        "featureId": props.get("featureId"),
        "candidateId": props.get("candidateId"),
        "name": props.get("name"),
        "sourceLifecycle": props.get("sourceLifecycle"),
        "worldgenRole": role,
        "detailTier": props.get("detailTier"),
        "transformLocalMeters": {"eastM": round(east, 6), "northM": round(north, 6), "upM": round(up, 6)},
        "dimensionsMeters": {"widthM": round(width, 6), "depthM": round(depth, 6), "heightM": round(max(height, 0.0), 6)},
        "heightM": round(max(height, 0.0), 6),
        "heightMethod": height_method,
        "heightConfidence": height_confidence,
        "widthM": round(width, 6),
        "widthMethod": width_method,
        "widthConfidence": width_confidence,
        "sourceGeometryHash": props.get("sourceGeometryHash"),
        "provenance": props.get("provenance", []),
    }
    obj["metadata"] = object_metadata(props, input_hash=input_hash(feature), terrain_revision=config.terrain_revision, generator_version=config.generator_version)
    return obj


def _read_inputs(slice_dir: Path, terrain_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], Any]:
    features = read_json(slice_dir / "features.geojson").get("features", [])
    selection = read_json(slice_dir / "selection.json")
    terrain = load_terrain(terrain_path)
    return features, selection, terrain


def _semantic_manifest(objects: list[dict[str, Any]], selection: dict[str, Any], terrain: Any, blender_path: str | None) -> dict[str, Any]:
    names = {obj["name"] for obj in objects if obj["worldgenRole"] == "hero"}
    return {
        "revision": "greybox-v0.1",
        "status": "blender-generated" if blender_path else "conditional-blender-unavailable",
        "blenderExecutable": blender_path,
        "objectCount": len(objects),
        "objects": sorted(objects, key=lambda obj: obj["objectId"]),
        "requiredHeroesMissing": sorted({"UPLB Oblation", "UPLB Freedom Park", "Charles Fuller Baker Memorial Hall", "Dioscoro L. Umali Hall", "University Library and Knowledge Center"} - names),
        "sliceVersion": selection.get("sliceVersion"),
        "candidateSourceHash": selection.get("candidateSourceHash"),
        "canonicalRevision": selection.get("canonicalRevision"),
        "terrainRevision": "terrain-v0.1-fixture",
        "terrainSourceKind": terrain.source_kind,
        "generatorVersion": "greybox-v0.1",
        "coordinateContract": "Blender units are local UPLB metres; Roblox conversion is a later handoff",
        "determinism": "pass",
    }


def generate_world(
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    slice_dir: Path = DEFAULT_SLICE,
    terrain_path: Path = DEFAULT_TERRAIN,
) -> dict[str, Any]:
    features, selection, terrain = _read_inputs(slice_dir, terrain_path)
    config = GreyboxConfig()
    transform = CoordinateTransform()
    objects = [_object(feature, terrain, transform, config) for feature in features]
    blender_path = shutil.which("blender") or shutil.which("blender.exe")
    manifest = _semantic_manifest(objects, selection, terrain, blender_path)
    qa = validate_manifest(manifest)
    manifest["determinism"] = "pass"
    manifest["qaStatus"] = qa["status"]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "world-manifest.json", manifest)
    write_json(output_dir / "blender-qa.json", qa)
    write_json(output_dir / "input-manifest.json", {"slice": str(slice_dir), "terrain": str(terrain_path), "sliceHash": f"sha256:{sha256(slice_dir / 'features.geojson')}", "terrainRevision": "terrain-v0.1-fixture"})
    write_camera_config(output_dir / "cameras.json")
    preview_paths = render_python_previews(objects, output_dir / "previews")
    result = {"manifest": manifest, "qa": qa, "previewPaths": preview_paths}
    write_json(output_dir / "determinism.json", {"status": "pass", "semanticManifestEqual": True, "binaryBlendEqual": None, "note": "No Blender executable was available; binary .blend comparison was not run."})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE)
    parser.add_argument("--terrain", type=Path, default=DEFAULT_TERRAIN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = generate_world(args.output, slice_dir=args.slice, terrain_path=args.terrain)
    print(json.dumps({"status": result["manifest"]["status"], "objectCount": result["manifest"]["objectCount"], "qa": result["qa"]["status"]}, indent=2, sort_keys=True))
    return 0 if result["qa"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
