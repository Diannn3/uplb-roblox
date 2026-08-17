"""Deterministic local-metre heightfield and shared ground-height API."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HeightField:
    product: str
    origin_east_m: float
    origin_north_m: float
    spacing_m: float
    values: tuple[tuple[float, ...], ...]
    nodata: float | None = None
    vertical_exaggeration: float = 1.0
    source_kind: str = "fixture"
    world_base_elevation_m: float | None = None
    vertical_reference_policy: str = "absolute-source-elevation"

    @property
    def rows(self) -> int:
        return len(self.values)

    @property
    def columns(self) -> int:
        return len(self.values[0]) if self.values else 0

    @property
    def min_elevation_m(self) -> float:
        return min(value for row in self.values for value in row if self.nodata is None or value != self.nodata)

    @property
    def max_elevation_m(self) -> float:
        return max(value for row in self.values for value in row if self.nodata is None or value != self.nodata)

    def ground_height(self, local_east_m: float, local_north_m: float) -> float:
        """Sample bilinearly in local metres; reject out-of-extent silently no more."""

        if self.rows < 2 or self.columns < 2 or self.spacing_m <= 0:
            raise ValueError("heightfield must have at least a 2x2 positive-spacing grid")
        x = (local_east_m - self.origin_east_m) / self.spacing_m
        y = (local_north_m - self.origin_north_m) / self.spacing_m
        if x < 0 or y < 0 or x > self.columns - 1 or y > self.rows - 1:
            raise ValueError(f"point outside terrain extent: east={local_east_m} north={local_north_m}")
        x0, y0 = min(int(math.floor(x)), self.columns - 2), min(int(math.floor(y)), self.rows - 2)
        dx, dy = x - x0, y - y0
        samples = (self.values[y0][x0], self.values[y0][x0 + 1], self.values[y0 + 1][x0], self.values[y0 + 1][x0 + 1])
        if self.nodata is not None and any(value == self.nodata for value in samples):
            raise ValueError("terrain sample intersects nodata")
        top = samples[0] * (1 - dx) + samples[1] * dx
        bottom = samples[2] * (1 - dx) + samples[3] * dx
        return (top * (1 - dy) + bottom * dy) * self.vertical_exaggeration

    def relative_ground_height(self, local_east_m: float, local_north_m: float) -> float:
        """Sample the same surface relative to the deterministic world base."""

        if self.world_base_elevation_m is None:
            raise ValueError("heightfield has no world base elevation")
        return self.ground_height(local_east_m, local_north_m) - self.world_base_elevation_m

    def to_dict(self) -> dict[str, Any]:
        return {
            "product": self.product,
            "originEastM": self.origin_east_m,
            "originNorthM": self.origin_north_m,
            "spacingM": self.spacing_m,
            "rows": self.rows,
            "columns": self.columns,
            "values": [list(row) for row in self.values],
            "nodata": self.nodata,
            "verticalExaggeration": self.vertical_exaggeration,
            "sourceKind": self.source_kind,
            "verticalReference": {
                "sourceDatum": "EGM96",
                "worldBaseElevationM": self.world_base_elevation_m,
                "policy": self.vertical_reference_policy,
                "elevationSemantics": "absolute-values-with-relative-sampling",
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HeightField":
        return cls(
            product=str(payload["product"]),
            origin_east_m=float(payload["originEastM"]),
            origin_north_m=float(payload["originNorthM"]),
            spacing_m=float(payload["spacingM"]),
            values=tuple(tuple(float(value) for value in row) for row in payload["values"]),
            nodata=None if payload.get("nodata") is None else float(payload["nodata"]),
            vertical_exaggeration=float(payload.get("verticalExaggeration", 1.0)),
            source_kind=str(payload.get("sourceKind", "fixture")),
            world_base_elevation_m=(
                None
                if (payload.get("verticalReference") or {}).get("worldBaseElevationM") is None
                else float((payload.get("verticalReference") or {})["worldBaseElevationM"])
            ),
            vertical_reference_policy=str((payload.get("verticalReference") or {}).get("policy", "absolute-source-elevation")),
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def read(cls, path: Path) -> "HeightField":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
