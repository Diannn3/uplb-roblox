from __future__ import annotations

from typing import Any

from shapely.geometry import shape
from shapely.ops import transform as shapely_transform
from pyproj import Transformer

from tools.geodata.transform import CoordinateTransform


_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)


def projected_geometry(geometry: dict[str, Any]) -> Any:
    return shapely_transform(_TO_UTM.transform, shape(geometry))


def local_representative(geometry: dict[str, Any], transform: CoordinateTransform) -> tuple[float, float]:
    point = shape(geometry).representative_point()
    east, north, _ = transform.wgs84_to_local(float(point.x), float(point.y))
    return east, north


def local_points(geometry: dict[str, Any], transform: CoordinateTransform) -> list[tuple[float, float]]:
    projected = projected_geometry(geometry)
    origin_e, origin_n = transform.origin_e, transform.origin_n
    points = [(float(x - origin_e), float(y - origin_n)) for x, y in projected.coords] if hasattr(projected, "coords") else []
    return points


def dimensions_m(geometry: dict[str, Any]) -> tuple[float, float]:
    bounds = projected_geometry(geometry).bounds
    return max(float(bounds[2] - bounds[0]), 0.01), max(float(bounds[3] - bounds[1]), 0.01)
