"""Generate a deterministic runtime lookup module from canonical features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .io import geometry_anchor, sha256, write_json
from .models import CanonicalFeature
from .transform import CoordinateTransform


def _lua_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _lua_number(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    return format(float(value), ".9f").rstrip("0").rstrip(".") or "0"


def generate_luau(features: Iterable[CanonicalFeature], transform: CoordinateTransform, source_hash: str) -> str:
    ordered = sorted(
        (feature for feature in features if geometry_anchor(feature.geometry) is not None),
        key=lambda feature: feature.id,
    )
    lines = [
        "-- GENERATED FILE: do not edit by hand.",
        f"-- Canonical source SHA-256: {source_hash}",
        "local CampusFeatures = {",
        f"    VERSION = {_lua_string('canonical-v1')},",
        f"    SOURCE_HASH = {_lua_string(source_hash)},",
        f"    FEATURE_COUNT = {len(ordered)},",
        "    FEATURES = {",
    ]
    for feature in ordered:
        anchor = geometry_anchor(feature.geometry)
        point = transform.wgs84_to_roblox(anchor[0], anchor[1])
        lines.extend(
            [
                f"        [{_lua_string(feature.id)}] = {{",
                f"            featureType = {_lua_string(feature.feature_type)},",
                f"            name = {_lua_string(feature.name)},",
                "            position = {",
                f"                x = {_lua_number(point.x)},",
                f"                y = {_lua_number(point.y)},",
                f"                z = {_lua_number(point.z)},",
                "            },",
                f"            verificationStatus = {_lua_string(feature.verification_status)},",
                "        },",
            ]
        )
    lines.extend(["    },", "}", "", "return CampusFeatures", ""])
    return "\n".join(lines)


def write_luau(path: Path, features: Iterable[CanonicalFeature], transform: CoordinateTransform, source_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_luau(features, transform, sha256(source_path)), encoding="utf-8", newline="\n")
