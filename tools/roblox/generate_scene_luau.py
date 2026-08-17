"""Generate the server-owned Luau scene module from a canonical scene specification.

The generator intentionally emits plain Luau data only. Runtime placement and
terrain writes remain server-owned in ``WorldGenerator.lua``. The generated
module is intentionally not placed in ReplicatedStorage because it contains a
large terrain heightfield and authoritative placement data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

GENERATOR_VERSION = "roblox-scene-luau-v0.1"


def _lua_string(value: str) -> str:
    # Emit ASCII-only Luau source.  Studio's script transport can corrupt raw
    # UTF-8 in a large Source payload; Luau's decimal byte escapes preserve the
    # original display text without introducing a parser ambiguity.
    escaped: list[str] = ['"']
    for byte in value.encode("utf-8"):
        if byte == 34:
            escaped.append('\\"')
        elif byte == 92:
            escaped.append("\\\\")
        elif byte == 10:
            escaped.append("\\n")
        elif byte == 13:
            escaped.append("\\r")
        elif byte == 9:
            escaped.append("\\t")
        elif 32 <= byte < 127:
            escaped.append(chr(byte))
        else:
            escaped.append(f"\\{byte:03d}")
    escaped.append('"')
    return "".join(escaped)


def _lua_number(value: int | float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite numeric value cannot be emitted: {value!r}")
    if number == 0:
        return "0"
    if number.is_integer() and abs(number) < 2**53:
        return str(int(number))
    return format(number, ".15g")


def _lua_literal(value: Any, indent: int = 0) -> str:
    """Emit a deterministic, readable Luau table literal."""

    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _lua_string(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _lua_number(value)
    if isinstance(value, list):
        if not value:
            return "{}"
        pad = " " * indent
        child_pad = " " * (indent + 2)
        entries = [f"{child_pad}{_lua_literal(item, indent + 2)}," for item in value]
        return "{\n" + "\n".join(entries) + f"\n{pad}}}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        pad = " " * indent
        child_pad = " " * (indent + 2)
        entries = []
        for key in sorted(value):
            entries.append(f"{child_pad}[{_lua_string(str(key))}] = {_lua_literal(value[key], indent + 2)},")
        return "{\n" + "\n".join(entries) + f"\n{pad}}}"
    raise TypeError(f"unsupported value for Luau generation: {type(value).__name__}")


def _lua_compact(value: Any) -> str:
    """Emit the same literal without formatting whitespace for Studio limits."""

    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _lua_string(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _lua_number(value)
    if isinstance(value, list):
        return "{" + ",".join(_lua_compact(item) for item in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"[{_lua_string(str(key))}]={_lua_compact(value[key])}" for key in sorted(value)) + "}"
    raise TypeError(f"unsupported value for Luau generation: {type(value).__name__}")


def _lua_runtime_literal(value: dict[str, Any]) -> str:
    """Keep top-level object entries on separate safe transfer lines."""

    lines = ["{"]
    for key in sorted(value):
        if key == "objects" and isinstance(value[key], list):
            lines.append(f"[{_lua_string(key)}]={{")
            lines.extend(f"{_lua_compact(item)}," for item in value[key])
            lines.append("},")
        else:
            lines.append(f"[{_lua_string(key)}]={_lua_compact(value[key])},")
    lines.append("}")
    return "\n".join(lines)


def _bounds(feature: dict[str, Any]) -> dict[str, float] | None:
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinatesLocalMeters") or []
    points: list[tuple[float, float]] = []

    def collect(value: Any) -> None:
        if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(coordinates)
    if not points:
        placement = feature.get("placement") or {}
        east = placement.get("eastM")
        north = placement.get("northM")
        if isinstance(east, (int, float)) and isinstance(north, (int, float)):
            # Point landmarks still need a deterministic, reviewable greybox
            # footprint until an approved asset footprint is available.
            half = 4.0 if feature.get("role") == "hero" else 2.0
            points = [(float(east) - half, float(north) - half), (float(east) + half, float(north) + half)]
    if not points:
        return None
    east_values = [point[0] for point in points]
    north_values = [point[1] for point in points]
    return {
        "minEastM": round(min(east_values), 6),
        "maxEastM": round(max(east_values), 6),
        "minNorthM": round(min(north_values), 6),
        "maxNorthM": round(max(north_values), 6),
    }


def _round_tree(value: Any, digits: int = 3) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [_round_tree(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: _round_tree(item, digits) for key, item in value.items()}
    return value


def prepare_scene(scene: dict[str, Any]) -> dict[str, Any]:
    """Create a compact runtime projection while retaining provenance fields.

    The canonical scene remains the audit artifact.  Roblox receives only the
    fields needed for deterministic placement, which keeps the generated
    ModuleScript well below Studio source-size and MCP payload limits.
    """

    source = json.loads(json.dumps(scene, sort_keys=True, ensure_ascii=False))
    metadata = source.setdefault("metadata", {})
    metadata["generatorVersion"] = GENERATOR_VERSION
    metadata["sourceSceneRevision"] = source.get("sceneRevision", "")

    objects: list[dict[str, Any]] = []
    for feature in source.get("objects", []):
        bounds = _bounds(feature)
        geometry = feature.get("geometry") or {}
        role = feature.get("role", "unknown")
        placement = feature.get("placement") or {}
        runtime: dict[str, Any] = {
            "footprintBoundsLocalMeters": bounds,
            # The server uses this to avoid ever treating a placeholder as an
            # approved asset or height claim.
            "placementAuthority": "server",
        }
        height = feature.get("height") or {}
        width = feature.get("width") or {}
        source_metadata = feature.get("metadata") or {}
        compact: dict[str, Any] = {
            "id": feature.get("id", feature.get("featureId", "")),
            "featureId": feature.get("featureId", ""),
            "candidateId": feature.get("candidateId", ""),
            "name": feature.get("name", ""),
            "role": role,
            "detailTier": feature.get("detailTier", 0),
            "sourceLifecycle": feature.get("sourceLifecycle", "candidate"),
            "materialClass": feature.get("materialClass", "default"),
            "placement": _round_tree(placement),
            "heightM": round(float(height.get("meters", 0.0)), 3),
            "widthM": round(float(width.get("meters", 0.0)), 3),
            # Keep source hashes and verification state visible at runtime.
            "provenance": {
                "sourceGeometryHash": source_metadata.get("sourceGeometryHash", ""),
                "verificationStatus": source_metadata.get("verificationStatus", "unknown"),
            },
            "runtime": _round_tree(runtime),
            "proxy": _round_tree(feature.get("proxy") or {}),
            "geometry": {"type": geometry.get("type", "")},
        }
        if role in {"road", "walkway", "water"}:
            centerline = geometry.get("centerlineCoordinatesLocalMeters3D") or []
            if not centerline:
                centerline = geometry.get("coordinatesLocalMeters") or []
            compact["geometry"]["centerlineCoordinatesLocalMeters3D"] = _round_tree(centerline)
        objects.append(compact)

    prepared = {
        "coordinateContract": source.get("coordinateContract", {}),
        "metadata": metadata,
        "sceneRevision": source.get("sceneRevision", ""),
        "status": source.get("status", "unknown"),
        "terrain": {
            key: _round_tree(source.get("terrain", {}).get(key))
            for key in (
                "columns",
                "rows",
                "originEastM",
                "originNorthM",
                "samplingResolutionM",
                "nativeResolutionM",
                "values",
                "relativeMinElevationM",
                "relativeMaxElevationM",
                "worldBaseElevationM",
                "sourceKind",
                "sourceHash",
                "archiveSha256",
                "hgtPayloadSha256",
                "processedHeightfieldSha256",
                "granule",
                "retrievalTimestamp",
                "revision",
                "verticalDatum",
                "verticalReference",
                "horizontalDatum",
                "localCRS",
                "interpolationPolicy",
            )
            if key in source.get("terrain", {})
        },
        "objects": objects,
    }
    prepared["runtimeContract"] = {
        "terrainWriter": "server",
        "coordinateTransform": "Shared.CoordinateTransform",
        "regenerationRoot": "GeneratedVerticalSlice_v01",
        "terrainResolutionStuds": 4,
        "sourceStatus": prepared["status"],
    }
    return prepared


def generate(scene_spec_path: Path, output_path: Path) -> dict[str, Any]:
    scene_path = Path(scene_spec_path).resolve()
    output = Path(output_path).resolve()
    source_bytes = scene_path.read_bytes()
    source = json.loads(source_bytes.decode("utf-8"))
    prepared = prepare_scene(source)
    body = _lua_runtime_literal(prepared)
    content = (
        "-- GENERATED FILE. Do not edit by hand.\n"
        f"-- Source: {scene_path.as_posix()}\n"
        f"-- Generator: {GENERATOR_VERSION}\n"
        f"-- Source SHA256: sha256:{hashlib.sha256(source_bytes).hexdigest()}\n\n"
        "return "
        + body
        + "\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    return {
        "output": output.as_posix(),
        "generatorVersion": GENERATOR_VERSION,
        "sourceSceneSpecSha256": f"sha256:{hashlib.sha256(source_bytes).hexdigest()}",
        "generatedLuauSha256": f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        "objectCount": len(prepared.get("objects", [])),
        "terrainRows": prepared.get("terrain", {}).get("rows", 0),
        "terrainColumns": prepared.get("terrain", {}).get("columns", 0),
        "status": "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--scene-spec", type=Path, default=root / "data" / "generated" / "worldgen-v0.1" / "scene-spec.json")
    parser.add_argument("--output", type=Path, default=root / "src" / "Server" / "Generated" / "WorldScene.lua")
    args = parser.parse_args()
    print(json.dumps(generate(args.scene_spec, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
