from __future__ import annotations

import json

import pytest

from tools.modeling.geometry_v2 import project_wgs84_geometry_to_local_meters
from tools.modeling.orientation import resolve_front_frame
from tools.modeling.registry import ROOT


def test_baker_reviewed_baseline_faces_freedom_park_side() -> None:
    snapshot = json.loads(
        (ROOT / "data/modeling/reference/baker-canonical-snapshot.geojson").read_text(encoding="utf-8")
    )
    projected = project_wgs84_geometry_to_local_meters(snapshot["feature"]["geometry"])
    ring = [(float(p[0]), float(p[1])) for p in projected["coordinatesLocalMeters"][0][:-1]]
    frame = resolve_front_frame(
        ring,
        {
            "policy": "reviewed-baseline",
            "confidence": "high",
            "reviewStatus": "reviewed",
            "baselineStartVertexIndex": 9,
            "baselineEndVertexIndex": 5,
            "frontAzimuthDegrees": 237.3,
            "evidenceIds": ["test"],
        },
    )
    assert frame.selection_method == "reviewed-baseline"
    assert frame.length_m == pytest.approx(29.336, abs=0.05)
    assert frame.outward_azimuth_degrees == pytest.approx(237.3, abs=0.3)
    assert frame.baseline_end_vertex_index == 5
