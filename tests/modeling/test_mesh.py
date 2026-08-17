import json
from pathlib import Path

import pytest

from tools.modeling.mesh import extrude_polygon, project_wgs84_ring_to_local_meters

ROOT = Path(__file__).resolve().parents[2]


def test_extrude_simple_square_is_deterministic() -> None:
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0), (0.0, 0.0)]
    first = extrude_polygon(ring, 6.0)
    second = extrude_polygon(ring, 6.0)
    assert first == second
    assert len(first.vertices) == 8
    assert first.triangle_equivalent >= 12


def test_invalid_height_is_rejected() -> None:
    with pytest.raises(ValueError):
        extrude_polygon([(0, 0), (1, 0), (0, 1)], 0)


def test_baker_projection_is_realistic_scale() -> None:
    snapshot = json.loads((ROOT / "data/modeling/reference/baker-canonical-snapshot.geojson").read_text(encoding="utf-8"))
    ring = snapshot["feature"]["geometry"]["coordinates"][0]
    local, _ = project_wgs84_ring_to_local_meters(ring)
    xs = [point[0] for point in local]
    ys = [point[1] for point in local]
    assert 30 < max(xs) - min(xs) < 100
    assert 30 < max(ys) - min(ys) < 100
