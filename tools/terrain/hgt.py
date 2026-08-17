"""Lightweight, deterministic readers for NASA HGT terrain tiles.

The reader intentionally handles only the HGT packaging used by SRTMGL1 and
NASADEM_HGT.  Product-specific archive selection lives here rather than in the
terrain compiler, while sampling remains in geographic WGS84 coordinates.
"""

from __future__ import annotations

import hashlib
import math
import re
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_TILE_NAME = re.compile(r"^(?P<ns>[NS])(?P<lat>\d{2})(?P<ew>[EW])(?P<lon>\d{3})\.hgt$", re.IGNORECASE)
_NODATA = -32768


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
    values: tuple[tuple[int, ...], ...]
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
        return sum(value == self.nodata for row in self.values for value in row)

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        product: str,
        expected_sha256: str | None = None,
    ) -> "HgtTile":
        path = Path(path)
        data = path.read_bytes()
        return cls._from_bytes(data, path.name, product=product, expected_sha256=expected_sha256)

    @classmethod
    def from_archive(
        cls,
        path: Path,
        *,
        product: str,
        expected_sha256: str | None = None,
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
        return cls._from_bytes(data, name, product=product, expected_sha256=expected_sha256)

    @classmethod
    def _from_bytes(
        cls,
        data: bytes,
        name: str,
        *,
        product: str,
        expected_sha256: str | None,
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
        raw = struct.unpack(f">{sample_count}h", data)
        values = tuple(tuple(raw[row * size : (row + 1) * size]) for row in range(size))
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
            self.values[y0][x0],
            self.values[y0][x0 + 1],
            self.values[y0 + 1][x0],
            self.values[y0 + 1][x0 + 1],
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
        return HgtTile.from_archive(path, product=cls.product, expected_sha256=expected_sha256) if path.suffix.lower() == ".zip" else HgtTile.from_file(path, product=cls.product, expected_sha256=expected_sha256)


class NasademHgtSource:
    product = "NASADEM_HGT.001"

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> HgtTile:
        return HgtTile.from_archive(path, product=cls.product, expected_sha256=expected_sha256) if path.suffix.lower() == ".zip" else HgtTile.from_file(path, product=cls.product, expected_sha256=expected_sha256)


def iter_hgt_members(path: Path) -> Iterable[str]:
    """List archive HGT members for acquisition diagnostics."""

    with zipfile.ZipFile(path) as archive:
        yield from sorted(info.filename for info in archive.infolist() if info.filename.lower().endswith(".hgt"))
