"""Lightweight, deterministic readers for NASA HGT terrain tiles.

The reader intentionally handles only the HGT packaging used by SRTMGL1 and
NASADEM_HGT.  Product-specific archive selection lives here rather than in the
terrain compiler, while sampling remains in geographic WGS84 coordinates.
"""

from __future__ import annotations

import hashlib
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


_TILE_NAME = re.compile(r"^(?P<ns>[NS])(?P<lat>\d{2})(?P<ew>[EW])(?P<lon>\d{3})\.hgt$", re.IGNORECASE)
_NODATA = -32768

# Both selected products are 1 arc-second rasters.  An HGT tile has one
# sample at each edge, therefore the documented 1-degree tile is 3601x3601.
# The reader keeps a permissive fixture mode so the tiny 3x3 test tiles remain
# useful, while production preprocessing passes the strict expected size.
PRODUCT_RASTER_SIZES = {
    "SRTMGL1.003": 3601,
    "NASADEM_HGT.001": 3601,
}


def _tile_origin(name: str) -> tuple[float, float]:
    match = _TILE_NAME.match(Path(name).name)
    if not match:
        raise ValueError(f"HGT filename must be a tile name such as N14E121.hgt: {name}")
    latitude = float(match.group("lat")) * (1 if match.group("ns").upper() == "N" else -1)
    longitude = float(match.group("lon")) * (1 if match.group("ew").upper() == "E" else -1)
    return longitude, latitude


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class HgtTile:
    """A single HGT tile with north-to-south, big-endian source semantics."""

    product: str
    west: float
    south: float
    size: int
    values: np.ndarray
    source_hash: str
    nodata: int = _NODATA
    source_kind: str = "real-nasa-raster"

    @property
    def east(self) -> float:
        return self.west + 1.0

    @property
    def north(self) -> float:
        return self.south + 1.0

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.west, self.south, self.east, self.north

    @property
    def nodata_count(self) -> int:
        return int(np.count_nonzero(self.values == self.nodata))

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        product: str,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> "HgtTile":
        path = Path(path)
        data = path.read_bytes()
        return cls._from_bytes(data, path.name, product=product, expected_sha256=expected_sha256, expected_size=expected_size)

    @classmethod
    def from_archive(
        cls,
        path: Path,
        *,
        product: str,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> "HgtTile":
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                info.filename
                for info in archive.infolist()
                if not info.is_dir() and info.filename.lower().endswith(".hgt")
            )
            if not names:
                raise ValueError(f"archive contains no .hgt member: {path}")
            if len(names) != 1:
                raise ValueError(f"archive must contain exactly one HGT tile, found {len(names)}")
            name = names[0]
            data = archive.read(name)
        return cls._from_bytes(data, name, product=product, expected_sha256=expected_sha256, expected_size=expected_size)

    @classmethod
    def _from_bytes(
        cls,
        data: bytes,
        name: str,
        *,
        product: str,
        expected_sha256: str | None,
        expected_size: int | None,
    ) -> "HgtTile":
        source_hash = _sha256_bytes(data)
        if expected_sha256 and source_hash != expected_sha256:
            raise ValueError(f"HGT checksum mismatch: expected {expected_sha256}, got {source_hash}")
        if len(data) == 0 or len(data) % 2:
            raise ValueError("HGT payload must contain a non-empty even number of bytes")
        sample_count = len(data) // 2
        size = math.isqrt(sample_count)
        if size < 2 or size * size != sample_count:
            raise ValueError(f"HGT payload does not contain a square grid: {len(data)} bytes")
        if expected_size is not None and size != expected_size:
            raise ValueError(f"HGT payload has {size}x{size} samples; expected {expected_size}x{expected_size}")
        values = np.frombuffer(data, dtype=">i2").reshape((size, size))
        west, south = _tile_origin(name)
        return cls(product=str(product), west=west, south=south, size=size, values=values, source_hash=source_hash)

    def sample(self, longitude: float, latitude: float) -> float:
        """Return bilinearly interpolated EGM96 metres, rejecting nodata."""

        if not (self.west <= longitude <= self.east and self.south <= latitude <= self.north):
            raise ValueError(f"point outside HGT tile extent: lon={longitude} lat={latitude}")
        x = (longitude - self.west) * (self.size - 1)
        y = (self.north - latitude) * (self.size - 1)
        x0 = min(int(math.floor(x)), self.size - 2)
        y0 = min(int(math.floor(y)), self.size - 2)
        dx, dy = x - x0, y - y0
        samples = (
            int(self.values[y0, x0]),
            int(self.values[y0, x0 + 1]),
            int(self.values[y0 + 1, x0]),
            int(self.values[y0 + 1, x0 + 1]),
        )
        if any(value == self.nodata for value in samples):
            raise ValueError("HGT sample intersects nodata")
        top = samples[0] * (1.0 - dx) + samples[1] * dx
        bottom = samples[2] * (1.0 - dx) + samples[3] * dx
        return float(top * (1.0 - dy) + bottom * dy)


class SrtmHgtSource:
    product = "SRTMGL1.003"

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> HgtTile:
        kwargs = {"product": cls.product, "expected_sha256": expected_sha256, "expected_size": PRODUCT_RASTER_SIZES[cls.product]}
        return HgtTile.from_archive(path, **kwargs) if path.suffix.lower() == ".zip" else HgtTile.from_file(path, **kwargs)


class NasademHgtSource:
    product = "NASADEM_HGT.001"

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> HgtTile:
        kwargs = {"product": cls.product, "expected_sha256": expected_sha256, "expected_size": PRODUCT_RASTER_SIZES[cls.product]}
        return HgtTile.from_archive(path, **kwargs) if path.suffix.lower() == ".zip" else HgtTile.from_file(path, **kwargs)


def iter_hgt_members(path: Path) -> Iterable[str]:
    """List archive HGT members for acquisition diagnostics."""

    with zipfile.ZipFile(path) as archive:
        yield from sorted(info.filename for info in archive.infolist() if info.filename.lower().endswith(".hgt"))
