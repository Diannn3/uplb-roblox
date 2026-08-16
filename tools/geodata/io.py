"""UTF-8, deterministic JSON and GeoJSON helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_feature_collection(path: Path, features: Iterable[dict[str, Any]], **metadata: Any) -> None:
    ordered = sorted(features, key=lambda feature: str(feature.get("id", "")))
    value = {"type": "FeatureCollection", **metadata, "features": ordered}
    write_json(path, value)


def geometry_bbox(geometry: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    if not geometry:
        return None

    coordinates = geometry.get("coordinates")
    if coordinates is None:
        return None

    values: list[tuple[float, float]] = []

    def visit(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
            isinstance(item, (int, float)) for item in value[:2]
        ):
            values.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(coordinates)
    if not values:
        return None
    xs, ys = zip(*values)
    return min(xs), min(ys), max(xs), max(ys)


def geometry_centroid(geometry: dict[str, Any] | None) -> tuple[float, float] | None:
    bounds = geometry_bbox(geometry)
    if bounds is None:
        return None
    west, south, east, north = bounds
    return (west + east) / 2.0, (south + north) / 2.0


def geometry_from_osm_points(points: list[dict[str, float]], polygon: bool = False) -> dict[str, Any] | None:
    coordinates = [[float(point["lon"]), float(point["lat"])] for point in points]
    if not coordinates:
        return None
    if len(coordinates) == 1:
        return {"type": "Point", "coordinates": coordinates[0]}
    if polygon and len(coordinates) >= 3:
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        return {"type": "Polygon", "coordinates": [coordinates]}
    return {"type": "LineString", "coordinates": coordinates}


def geometry_anchor(geometry: dict[str, Any] | None) -> tuple[float, float] | None:
    """Return a deterministic anchor without requiring a heavyweight GIS library."""

    return geometry_centroid(geometry)
