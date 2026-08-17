from __future__ import annotations

from tools.modeling.mesh import MeshData, box_mesh
from tools.modeling.topology import mesh_topology_report


def test_closed_box_is_watertight() -> None:
    report = mesh_topology_report(box_mesh(2, 2, 2))
    assert report["status"] == "pass"
    assert report["boundaryEdgeCount"] == 0
    assert report["watertight"] is True


def test_open_box_is_rejected() -> None:
    box = box_mesh(2, 2, 2)
    open_mesh = MeshData(box.vertices, box.faces[:-1])
    report = mesh_topology_report(open_mesh)
    assert report["status"] == "fail"
    assert report["boundaryEdgeCount"] > 0
    assert report["watertight"] is False
