from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from shapely.geometry import Polygon


@dataclass(frozen=True)
class FacadeFrame:
    edge_index: int
    length_m: float
    start: tuple[float, float]
    end: tuple[float, float]
    midpoint: tuple[float, float]
    tangent: tuple[float, float]
    outward: tuple[float, float]
    outward_azimuth_degrees: float
    selection_method: str
    confidence: str
    baseline_end_vertex_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "edgeIndex": self.edge_index,
            "lengthM": round(self.length_m, 6),
            "start": [round(v, 6) for v in self.start],
            "end": [round(v, 6) for v in self.end],
            "midpoint": [round(v, 6) for v in self.midpoint],
            "tangent": [round(v, 9) for v in self.tangent],
            "outward": [round(v, 9) for v in self.outward],
            "outwardAzimuthDegrees": round(self.outward_azimuth_degrees, 6),
            "selectionMethod": self.selection_method,
            "confidence": self.confidence,
            "baselineEndVertexIndex": self.baseline_end_vertex_index,
        }


def _open_ring(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    ring = [(float(x), float(y)) for x, y in points]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    if len(ring) < 3:
        raise ValueError("facade orientation requires at least three footprint vertices")
    return ring


def _angle_distance(a: float, b: float) -> float:
    delta = (a - b + 180.0) % 360.0 - 180.0
    return abs(delta)


def _frame(ring: list[tuple[float, float]], index: int, *, selection_method: str, confidence: str) -> FacadeFrame:
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("invalid footprint for facade orientation")
    if index < 0 or index >= len(ring):
        raise ValueError(f"front edge index {index} is outside footprint edge range")
    start = ring[index]
    end = ring[(index + 1) % len(ring)]
    length = math.dist(start, end)
    if length <= 1e-8:
        raise ValueError("zero-length facade edge")
    tangent = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
    outward = (tangent[1], -tangent[0]) if polygon.exterior.is_ccw else (-tangent[1], tangent[0])
    azimuth = math.degrees(math.atan2(outward[0], outward[1])) % 360.0  # clockwise from north
    return FacadeFrame(
        edge_index=index,
        length_m=length,
        start=start,
        end=end,
        midpoint=((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0),
        tangent=tangent,
        outward=outward,
        outward_azimuth_degrees=azimuth,
        selection_method=selection_method,
        confidence=confidence,
    )


def _baseline_frame(
    ring: list[tuple[float, float]],
    start_index: int,
    end_index: int,
    *,
    front_azimuth_degrees: float,
    selection_method: str,
    confidence: str,
) -> FacadeFrame:
    """Create a facade frame from a reviewed frontage baseline.

    Stepped facades can span several short footprint edges. The baseline is a
    review construct only; it never rewrites canonical footprint geometry.
    """
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("invalid footprint for facade orientation")
    if start_index < 0 or start_index >= len(ring) or end_index < 0 or end_index >= len(ring):
        raise ValueError("reviewed baseline vertex index is outside footprint range")
    if start_index == end_index:
        raise ValueError("reviewed baseline requires two distinct vertices")

    start = ring[start_index]
    end = ring[end_index]
    length = math.dist(start, end)
    if length <= 1e-8:
        raise ValueError("zero-length reviewed facade baseline")

    tangent = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
    normals = ((tangent[1], -tangent[0]), (-tangent[1], tangent[0]))
    target = float(front_azimuth_degrees) % 360.0

    def normal_azimuth(normal: tuple[float, float]) -> float:
        return math.degrees(math.atan2(normal[0], normal[1])) % 360.0

    outward = min(normals, key=lambda normal: _angle_distance(normal_azimuth(normal), target))
    azimuth = normal_azimuth(outward)
    return FacadeFrame(
        edge_index=start_index,
        length_m=length,
        start=start,
        end=end,
        midpoint=((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0),
        tangent=tangent,
        outward=outward,
        outward_azimuth_degrees=azimuth,
        selection_method=selection_method,
        confidence=confidence,
        baseline_end_vertex_index=end_index,
    )


def edge_frames(ring: Iterable[tuple[float, float]]) -> tuple[FacadeFrame, ...]:
    opened = _open_ring(ring)
    return tuple(
        _frame(opened, index, selection_method="edge-enumeration", confidence="not-reviewed")
        for index in range(len(opened))
    )


def resolve_front_frame(
    ring: Iterable[tuple[float, float]],
    orientation: dict[str, Any],
    *,
    allow_proxy: bool = False,
) -> FacadeFrame:
    """Resolve a building front facade using an explicit evidence-aware policy.

    High-fidelity assets should use a reviewed policy. ``longest-edge-proxy`` is
    retained only for low-confidence backwards-compatible prototypes.
    """

    opened = _open_ring(ring)
    policy = str(orientation.get("policy", "unknown"))
    confidence = str(orientation.get("confidence", "unknown"))
    reviewed = str(orientation.get("reviewStatus", "unreviewed"))

    if policy == "unknown":
        if not allow_proxy:
            raise ValueError("front facade orientation is unresolved")
        policy = "longest-edge-proxy"

    if policy == "longest-edge-proxy":
        if not allow_proxy:
            raise ValueError("longest-edge-proxy is not permitted for this production gate")
        lengths = [math.dist(point, opened[(idx + 1) % len(opened)]) for idx, point in enumerate(opened)]
        index = max(range(len(opened)), key=lambda idx: (lengths[idx], -idx))
        return _frame(
            opened,
            index,
            selection_method="longest-edge-proxy",
            confidence=confidence or "proxy",
        )

    reviewed_policies = {
        "reviewed-source-edge",
        "reviewed-azimuth",
        "reviewed-baseline",
        "entrance-anchor",
        "legacy-model-derived",
        "field-measured",
    }
    if policy not in reviewed_policies:
        raise ValueError(f"unsupported front facade orientation policy: {policy}")
    if reviewed != "reviewed":
        raise ValueError(f"orientation policy {policy} requires reviewStatus=reviewed")

    if policy == "reviewed-baseline":
        required = ("baselineStartVertexIndex", "baselineEndVertexIndex", "frontAzimuthDegrees")
        missing = [key for key in required if key not in orientation]
        if missing:
            raise ValueError("reviewed-baseline requires " + ", ".join(missing))
        return _baseline_frame(
            opened,
            int(orientation["baselineStartVertexIndex"]),
            int(orientation["baselineEndVertexIndex"]),
            front_azimuth_degrees=float(orientation["frontAzimuthDegrees"]),
            selection_method=policy,
            confidence=confidence,
        )


    if "edgeIndex" in orientation:
        return _frame(
            opened,
            int(orientation["edgeIndex"]),
            selection_method=policy,
            confidence=confidence,
        )

    if "frontAzimuthDegrees" in orientation:
        target = float(orientation["frontAzimuthDegrees"]) % 360.0
        frames = [
            _frame(opened, idx, selection_method=policy, confidence=confidence)
            for idx in range(len(opened))
        ]
        return min(frames, key=lambda row: (_angle_distance(row.outward_azimuth_degrees, target), row.edge_index))

    if policy == "entrance-anchor" and "entranceAnchorLocalMeters" in orientation:
        anchor = orientation["entranceAnchorLocalMeters"]
        if not isinstance(anchor, list) or len(anchor) < 2:
            raise ValueError("entranceAnchorLocalMeters must be [east,north]")
        ax, ay = float(anchor[0]), float(anchor[1])
        frames = [
            _frame(opened, idx, selection_method=policy, confidence=confidence)
            for idx in range(len(opened))
        ]
        return min(frames, key=lambda row: (math.dist(row.midpoint, (ax, ay)), row.edge_index))

    raise ValueError(f"orientation policy {policy} requires edgeIndex, frontAzimuthDegrees, or an entrance anchor")
