"""WGS84 -> UTM 51N -> local metres -> Roblox studs transform contract."""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import Transformer


WGS84 = "EPSG:4326"
UTM51N = "EPSG:32651"


@dataclass(frozen=True)
class ProjectConfig:
    origin_lon: float = 121.24155
    origin_lat: float = 14.16500
    origin_elevation_m: float = 0.0
    meters_per_stud: float = 0.28
    projected_crs: str = UTM51N

    @property
    def studs_per_meter(self) -> float:
        return 1.0 / self.meters_per_stud


@dataclass(frozen=True)
class RobloxPoint:
    x: float
    y: float
    z: float


class CoordinateTransform:
    """Explicit, invertible coordinate conversion used by all ingest tools."""

    def __init__(self, config: ProjectConfig | None = None) -> None:
        self.config = config or ProjectConfig()
        self._to_projected = Transformer.from_crs(WGS84, self.config.projected_crs, always_xy=True)
        self._to_wgs84 = Transformer.from_crs(self.config.projected_crs, WGS84, always_xy=True)
        self.origin_e, self.origin_n = self._to_projected.transform(
            self.config.origin_lon, self.config.origin_lat
        )

    def wgs84_to_local(
        self, lon: float, lat: float, elevation_m: float | None = None
    ) -> tuple[float, float, float]:
        easting, northing = self._to_projected.transform(lon, lat)
        elevation = self.config.origin_elevation_m if elevation_m is None else elevation_m
        return (
            easting - self.origin_e,
            northing - self.origin_n,
            elevation - self.config.origin_elevation_m,
        )

    def local_to_wgs84(self, east_m: float, north_m: float) -> tuple[float, float]:
        return self._to_wgs84.transform(self.origin_e + east_m, self.origin_n + north_m)

    def local_to_roblox(self, east_m: float, north_m: float, up_m: float = 0.0) -> RobloxPoint:
        scale = self.config.studs_per_meter
        return RobloxPoint(east_m * scale, up_m * scale, -north_m * scale)

    def roblox_to_local(self, point: RobloxPoint) -> tuple[float, float, float]:
        scale = self.config.meters_per_stud
        return point.x * scale, -point.z * scale, point.y * scale

    def wgs84_to_roblox(
        self,
        lon: float,
        lat: float,
        elevation_m: float | None = None,
    ) -> RobloxPoint:
        east_m, north_m, up_m = self.wgs84_to_local(lon, lat, elevation_m)
        return self.local_to_roblox(east_m, north_m, up_m)

    def roblox_to_wgs84(self, point: RobloxPoint) -> tuple[float, float, float]:
        east_m, north_m, up_m = self.roblox_to_local(point)
        lon, lat = self.local_to_wgs84(east_m, north_m)
        return lon, lat, up_m + self.config.origin_elevation_m

    def roundtrip_error_m(self, lon: float, lat: float) -> float:
        east_m, north_m, _ = self.wgs84_to_local(lon, lat)
        lon2, lat2 = self.local_to_wgs84(east_m, north_m)
        e1, n1 = self._to_projected.transform(lon, lat)
        e2, n2 = self._to_projected.transform(lon2, lat2)
        return ((e2 - e1) ** 2 + (n2 - n1) ** 2) ** 0.5
