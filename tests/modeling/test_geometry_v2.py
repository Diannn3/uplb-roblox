from __future__ import annotations

from tools.modeling.geometry_v2 import extrude_local_geometry
from tools.modeling.topology import mesh_topology_report


def test_polygon_with_hole_extrudes_watertight() -> None:
    projected = {
        "type": "Polygon",
        "coordinatesLocalMeters": [
            [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
            [[3, 3], [3, 7], [7, 7], [7, 3], [3, 3]],
        ],
    }
    mesh = extrude_local_geometry(projected, height_m=4.0)
    report = mesh_topology_report(mesh)
    assert report["status"] == "pass"
    assert report["watertight"] is True
    assert report["connectedComponentCount"] == 1


def test_multipolygon_extrudes_as_two_watertight_components() -> None:
    projected = {
        "type": "MultiPolygon",
        "coordinatesLocalMeters": [
            [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
            [[[10, 0], [14, 0], [14, 4], [10, 4], [10, 0]]],
        ],
    }
    mesh = extrude_local_geometry(projected, height_m=3.0)
    report = mesh_topology_report(mesh)
    assert report["status"] == "pass"
    assert report["watertight"] is True
    assert report["connectedComponentCount"] == 2
