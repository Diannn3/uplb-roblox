#!/usr/bin/env python3
"""Research transform contract: WGS84 -> UTM 51N -> local metres -> Roblox studs."""
from dataclasses import dataclass
from pyproj import Transformer
WGS84='EPSG:4326'; UTM51N='EPSG:32651'
ORIGIN_LON=121.24155; ORIGIN_LAT=14.16500
STUDS_PER_METER=3.5714285714285716  # project scale: 0.28 m/stud, explicitly configurable
_to_utm=Transformer.from_crs(WGS84,UTM51N,always_xy=True)
_to_wgs=Transformer.from_crs(UTM51N,WGS84,always_xy=True)
ORIGIN_E,ORIGIN_N=_to_utm.transform(ORIGIN_LON,ORIGIN_LAT)
@dataclass(frozen=True)
class RobloxPoint: x:float; y:float; z:float
def wgs84_to_local(lon,lat,elevation_m=0.0):
    e,n=_to_utm.transform(lon,lat); return e-ORIGIN_E,n-ORIGIN_N,elevation_m
def local_to_wgs84(east_m,north_m): return _to_wgs.transform(ORIGIN_E+east_m,ORIGIN_N+north_m)
def wgs84_to_roblox(lon,lat,elevation_m=0.0,datum_elevation_m=0.0):
    east,north,z=wgs84_to_local(lon,lat,elevation_m-datum_elevation_m); s=STUDS_PER_METER
    return RobloxPoint(east*s,z*s,-north*s)
def roundtrip_error_m(lon,lat):
    e,n,_=wgs84_to_local(lon,lat); lon2,lat2=local_to_wgs84(e,n)
    e1,n1=_to_utm.transform(lon,lat); e2,n2=_to_utm.transform(lon2,lat2)
    return ((e2-e1)**2+(n2-n1)**2)**0.5
if __name__=='__main__':
    points=[(121.24155,14.165),(121.24173,14.16128),(121.24389,14.16049),(121.225,14.145),(121.265,14.185)]
    print(f'Origin UTM51N: E={ORIGIN_E:.3f} N={ORIGIN_N:.3f}')
    worst=0.0
    for lon,lat in points:
        loc=wgs84_to_local(lon,lat); rob=wgs84_to_roblox(lon,lat); err=roundtrip_error_m(lon,lat); worst=max(worst,err)
        print(f'{lat:.6f},{lon:.6f} local=({loc[0]:.3f},{loc[1]:.3f})m roblox={rob} roundtrip={err:.9f}m')
    assert worst < 1e-5, worst
