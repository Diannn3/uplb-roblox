from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class FacadeBay:
    edge_index: int
    bay_index: int
    floor_index: int
    center_x: float
    center_y: float
    base_z: float
    yaw_degrees: float
    bay_width_m: float
    module_width_m: float
    module_height_m: float
    sill_height_m: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _open_ring(ring: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    points = list(ring)
    if len(points) >= 2 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        raise ValueError("facade ring must contain at least three distinct points")
    return points


def generate_facade_bays(
    ring: Iterable[tuple[float, float]],
    *,
    floors: int,
    floor_height_m: float,
    target_bay_width_m: float,
    module_width_ratio: float = 0.58,
    module_height_m: float = 1.4,
    sill_height_m: float = 0.9,
    minimum_edge_m: float = 1.2,
) -> list[FacadeBay]:
    """Generate deterministic facade-module placement hints.

    This produces a *layout plan*, not architectural truth. Real buildings should
    override bay counts/door positions whenever measured/reference evidence exists.
    """

    if floors < 1 or floor_height_m <= 0 or target_bay_width_m <= 0:
        raise ValueError("floors and dimensions must be positive")
    if not 0 < module_width_ratio <= 1:
        raise ValueError("module_width_ratio must be within (0, 1]")
    points = _open_ring(ring)
    placements: list[FacadeBay] = []
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < minimum_edge_m:
            continue
        bay_count = max(1, int(round(length / target_bay_width_m)))
        bay_width = length / bay_count
        ux, uy = dx / length, dy / length
        yaw = math.degrees(math.atan2(dy, dx))
        module_width = bay_width * module_width_ratio
        for bay_index in range(bay_count):
            distance = (bay_index + 0.5) * bay_width
            cx = start[0] + ux * distance
            cy = start[1] + uy * distance
            for floor_index in range(floors):
                placements.append(
                    FacadeBay(
                        edge_index=edge_index,
                        bay_index=bay_index,
                        floor_index=floor_index,
                        center_x=round(cx, 6),
                        center_y=round(cy, 6),
                        base_z=round(floor_index * floor_height_m, 6),
                        yaw_degrees=round(yaw, 6),
                        bay_width_m=round(bay_width, 6),
                        module_width_m=round(module_width, 6),
                        module_height_m=module_height_m,
                        sill_height_m=sill_height_m,
                    )
                )
    return placements
