"""Official NASA terrain product metadata used by the dual-source pipeline."""

from __future__ import annotations

PRODUCT_SOURCES = {
    "srtm": {
        "product": "SRTMGL1.003",
        "shortName": "SRTMGL1",
        "version": "003",
        "provider": "NASA JPL / NASA Earthdata LP DAAC",
        "resolutionM": 30,
        "doi": "10.5067/MEASURES/SRTM/SRTMGL1.003",
        "landingPage": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003",
        "citation": "NASA JPL; NASA Land Processes Distributed Active Archive Center (LP DAAC), SRTMGL1.003",
        "rights": "NASA Earthdata open data policy; cite the DOI; no credentials or raw bulk data committed",
        "redistribution": "Allowed with citation; do not imply NASA endorsement",
        "authRequirement": "Earthdata Login required for download; no credentials stored",
        "acquisitionRoute": "Earthdata Search/Earthdata Cloud supported route; retired LP DAAC Data Pool is not used",
        "horizontalCRS": "EPSG:4326",
        "horizontalDatum": "WGS84",
        "verticalDatum": "EGM96",
        "verticalUnits": "metres",
        "nodata": "Version 3.0 has no voids; historical -32768 is not expected",
    },
    "nasadem": {
        "product": "NASADEM_HGT.001",
        "shortName": "NASADEM_HGT",
        "version": "001",
        "provider": "NASA JPL / NASA Earthdata LP DAAC",
        "resolutionM": 30,
        "doi": "10.5067/MEASURES/NASADEM/NASADEM_HGT.001",
        "landingPage": "https://doi.org/10.5067/MEASURES/NASADEM/NASADEM_HGT.001",
        "citation": "NASA JPL. (2020). NASADEM Merged DEM Global 1 arc second V001 [Dataset]. NASA LP DAAC.",
        "rights": "NASA Earthdata open data policy; public-domain/open reuse with citation requested",
        "redistribution": "Allowed with citation; do not imply NASA endorsement",
        "authRequirement": "Earthdata Login required for download; no credentials stored",
        "acquisitionRoute": "Earthdata Search/Earthdata Cloud supported route; retired LP DAAC Data Pool is not used",
        "horizontalCRS": "EPSG:4326",
        "horizontalDatum": "WGS84",
        "verticalDatum": "EGM96",
        "verticalUnits": "metres",
        "nodata": "Product metadata must be checked per granule before processing",
    },
}


def product_source(name: str) -> dict[str, str | int]:
    try:
        return dict(PRODUCT_SOURCES[name.lower()])
    except KeyError as exc:
        raise ValueError(f"unsupported terrain product: {name}") from exc
