from __future__ import annotations

from typing import Any, Iterable

from pyproj import Transformer
from shapely import constrained_delaunay_triangles
from shapely.geometry import MultiPolygon, Polygon

from .mesh import MeshData, merge_meshes

WGS84_TO_UTM51 = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)


def _open_ring(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    result = [(float(x), float(y)) for x, y in points]
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    if len(result) < 3:
        raise ValueError("polygon ring requires at least 3 distinct points")
    return result


def _project_ring(ring: Iterable[Iterable[float]]) -> list[tuple[float, float]]:
    return _open_ring(
        WGS84_TO_UTM51.transform(float(point[0]), float(point[1]))
        for point in ring
    )


def _project_geometry_absolute(geometry: dict[str, Any]) -> Polygon | MultiPolygon:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if geometry_type == "Polygon":
        if not coordinates:
            raise ValueError("empty Polygon geometry")
        shell = _project_ring(coordinates[0])
        holes = [_project_ring(ring) for ring in coordinates[1:]]
        polygon = Polygon(shell, holes)
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError("invalid projected Polygon geometry")
        return polygon
    if geometry_type == "MultiPolygon":
        polygons = []
        for child in coordinates:
            if not child:
                continue
            shell = _project_ring(child[0])
            holes = [_project_ring(ring) for ring in child[1:]]
            polygon = Polygon(shell, holes)
            if not polygon.is_valid or polygon.area <= 0:
                raise ValueError("invalid projected MultiPolygon component")
            polygons.append(polygon)
        if not polygons:
            raise ValueError("empty MultiPolygon geometry")
        result = MultiPolygon(polygons)
        if not result.is_valid or result.area <= 0:
            raise ValueError("invalid projected MultiPolygon geometry")
        return result
    raise ValueError(f"unsupported building geometry type: {geometry_type!r}")


def _ring_local(ring: Any, origin: tuple[float, float]) -> list[list[float]]:
    return [[float(x) - origin[0], float(y) - origin[1]] for x, y in _open_ring(ring.coords)] + [
        [float(ring.coords[0][0]) - origin[0], float(ring.coords[0][1]) - origin[1]]
    ]


def project_wgs84_geometry_to_local_meters(geometry: dict[str, Any]) -> dict[str, Any]:
    projected = _project_geometry_absolute(geometry)
    centroid = projected.centroid
    origin = (float(centroid.x), float(centroid.y))

    if isinstance(projected, Polygon):
        coords = [_ring_local(projected.exterior, origin)]
        coords.extend(_ring_local(interior, origin) for interior in projected.interiors)
        return {
            "type": "Polygon",
            "coordinatesLocalMeters": coords,
            "originUtm51": [origin[0], origin[1]],
        }

    multi_coords: list[list[list[list[float]]]] = []
    for polygon in projected.geoms:
        child = [_ring_local(polygon.exterior, origin)]
        child.extend(_ring_local(interior, origin) for interior in polygon.interiors)
        multi_coords.append(child)
    return {
        "type": "MultiPolygon",
        "coordinatesLocalMeters": multi_coords,
        "originUtm51": [origin[0], origin[1]],
    }


def _vertex_table() -> tuple[list[tuple[float, float, float]], dict[tuple[float, float, float], int]]:
    return [], {}


def _append_vertex(
    vertices: list[tuple[float, float, float]],
    table: dict[tuple[float, float, float], int],
    point: tuple[float, float],
    z: float,
) -> int:
    key = (round(float(point[0]), 8), round(float(point[1]), 8), round(float(z), 8))
    if key not in table:
        table[key] = len(vertices)
        vertices.append((float(point[0]), float(point[1]), float(z)))
    return table[key]


def extrude_polygon_with_holes(
    shell: Iterable[tuple[float, float]],
    holes: Iterable[Iterable[tuple[float, float]]] = (),
    *,
    height_m: float,
    base_z: float = 0.0,
) -> MeshData:
    if height_m <= 0:
        raise ValueError("height_m must be positive")
    shell_open = _open_ring(shell)
    holes_open = [_open_ring(ring) for ring in holes]
    polygon = Polygon(shell_open, holes_open)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("footprint must be a valid positive-area polygon")

    vertices, table = _vertex_table()
    faces: list[tuple[int, ...]] = []
    top_z = base_z + height_m

    # Side walls. For holes we reverse winding relative to the exterior ring so
    # face orientation stays outward from the solid volume.
    rings = [(list(polygon.exterior.coords), False)] + [(list(r.coords), True) for r in polygon.interiors]
    for coords, is_hole in rings:
        points = _open_ring(coords)
        for idx, point in enumerate(points):
            nxt = points[(idx + 1) % len(points)]
            b0 = _append_vertex(vertices, table, point, base_z)
            b1 = _append_vertex(vertices, table, nxt, base_z)
            t1 = _append_vertex(vertices, table, nxt, top_z)
            t0 = _append_vertex(vertices, table, point, top_z)
            face = (b0, b1, t1, t0)
            faces.append(tuple(reversed(face)) if is_hole else face)

    triangles = constrained_delaunay_triangles(polygon)
    for triangle in triangles.geoms:
        representative = triangle.representative_point()
        if not polygon.covers(representative):
            continue
        coords = _open_ring(list(triangle.exterior.coords))
        bottom = tuple(_append_vertex(vertices, table, point, base_z) for point in coords)
        top = tuple(_append_vertex(vertices, table, point, top_z) for point in coords)
        faces.append(tuple(reversed(bottom)))
        faces.append(top)

    return MeshData(tuple(vertices), tuple(faces))


def extrude_local_geometry(projected: dict[str, Any], *, height_m: float, base_z: float = 0.0) -> MeshData:
    geometry_type = projected.get("type")
    coordinates = projected.get("coordinatesLocalMeters") or []
    if geometry_type == "Polygon":
        shell = _open_ring((float(p[0]), float(p[1])) for p in coordinates[0])
        holes = [_open_ring((float(p[0]), float(p[1])) for p in ring) for ring in coordinates[1:]]
        return extrude_polygon_with_holes(shell, holes, height_m=height_m, base_z=base_z)
    if geometry_type == "MultiPolygon":
        meshes = []
        for polygon in coordinates:
            shell = _open_ring((float(p[0]), float(p[1])) for p in polygon[0])
            holes = [_open_ring((float(p[0]), float(p[1])) for p in ring) for ring in polygon[1:]]
            meshes.append(extrude_polygon_with_holes(shell, holes, height_m=height_m, base_z=base_z))
        return merge_meshes(meshes)
    raise ValueError(f"unsupported local building geometry type: {geometry_type!r}")
