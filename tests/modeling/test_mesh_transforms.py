from __future__ import annotations

import math

from tools.modeling.mesh import box_mesh, gable_prism_mesh, merge_meshes, mesh_bounds, transform_mesh


def test_transform_and_merge_preserve_finite_geometry() -> None:
    mesh = transform_mesh(box_mesh(2, 4, 6), translation=(10, -4, 3))
    bounds = mesh_bounds(mesh)
    assert bounds["size"] == (2.0, 4.0, 6.0)
    merged = merge_meshes([mesh, mesh])
    assert len(merged.vertices) == len(mesh.vertices) * 2
    assert all(math.isfinite(value) for vertex in merged.vertices for value in vertex)


def test_gable_prism_has_requested_height() -> None:
    mesh = gable_prism_mesh(
        10,
        20,
        eave_z=8,
        ridge_z=10,
        center_xy=(0, 0),
        tangent_xy=(1, 0),
        outward_xy=(0, 1),
    )
    bounds = mesh_bounds(mesh)
    assert bounds["size"] == (10.0, 20.0, 2.0)
