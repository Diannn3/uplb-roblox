from __future__ import annotations

import pytest

from tools.modeling.orientation import resolve_front_frame

RING = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]


def test_proxy_orientation_is_explicitly_opt_in() -> None:
    with pytest.raises(ValueError):
        resolve_front_frame(RING, {"policy": "longest-edge-proxy", "confidence": "proxy", "reviewStatus": "unreviewed"})
    frame = resolve_front_frame(
        RING,
        {"policy": "longest-edge-proxy", "confidence": "proxy", "reviewStatus": "unreviewed"},
        allow_proxy=True,
    )
    assert frame.selection_method == "longest-edge-proxy"
    assert frame.edge_index == 0


def test_reviewed_edge_is_deterministic() -> None:
    frame = resolve_front_frame(
        RING,
        {"policy": "reviewed-source-edge", "edgeIndex": 2, "confidence": "high", "reviewStatus": "reviewed"},
    )
    assert frame.edge_index == 2
    assert frame.selection_method == "reviewed-source-edge"


def test_reviewed_policy_must_actually_be_reviewed() -> None:
    with pytest.raises(ValueError, match="reviewStatus=reviewed"):
        resolve_front_frame(
            RING,
            {"policy": "reviewed-source-edge", "edgeIndex": 1, "confidence": "high", "reviewStatus": "unreviewed"},
        )


def test_reviewed_azimuth_selects_closest_outward_edge() -> None:
    frame = resolve_front_frame(
        RING,
        {"policy": "reviewed-azimuth", "frontAzimuthDegrees": 180.0, "confidence": "high", "reviewStatus": "reviewed"},
    )
    assert abs(frame.outward_azimuth_degrees - 180.0) < 1e-6
