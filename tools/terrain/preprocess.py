"""DEM preprocessing and explicit deterministic fixture harness."""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
from typing import Any

from tools.geodata.io import geometry_bbox, write_json
from tools.geodata.transform import CoordinateTransform, ProjectConfig

from .hgt import HgtTile, PRODUCT_RASTER_SIZES
from .sample import HeightField
from .sources import product_source


def build_fixture_heightfield(product: str, output_dir: Path | None = None) -> HeightField:
    """Build a tiny synthetic macro-slope fixture, never presented as NASA data."""

    source = product_source(product)
    offset = 0.0 if product.lower() == "srtm" else 0.65
    spacing = 30.0
    values = tuple(
        tuple(100.0 + offset + (x * 0.18) + (y * 0.11) for x in range(45))
        for y in range(45)
    )
    world_base = math.floor(min(value for row in values for value in row) - 2.0)
    field = HeightField(
        product=str(source["product"]),
        origin_east_m=-600.0,
        origin_north_m=-1000.0,
        spacing_m=spacing,
        values=values,
        source_kind="synthetic-fixture",
        vertical_exaggeration=1.0,
        world_base_elevation_m=world_base,
        vertical_reference_policy="fixture-minimum-minus-padding",
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        field.write(output_dir / "heightfield.json")
        manifest = {
            **source,
            "sourceKind": "synthetic-fixture",
            "sourceHash": None,
            "processing": {"targetCRS": "EPSG:32651", "localCoordinates": True, "verticalExaggeration": 1.0, "crop": "fixture-only"},
            "verticalReference": {"sourceDatum": "EGM96", "worldBaseElevationM": world_base, "policy": "fixture-minimum-minus-padding"},
            "heightfield": "heightfield.json",
            "status": "fixture-only",
        }
        (output_dir / "terrain-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return field


def _aoi_local_bounds(aoi_path: Path, transform: CoordinateTransform) -> tuple[float, float, float, float]:
    payload = json.loads(Path(aoi_path).read_text(encoding="utf-8"))
    bounds = [geometry_bbox(feature.get("geometry")) for feature in payload.get("features", [])]
    bounds = [item for item in bounds if item is not None]
    if not bounds:
        raise ValueError(f"AOI has no geometry: {aoi_path}")
    west = min(item[0] for item in bounds)
    south = min(item[1] for item in bounds)
    east = max(item[2] for item in bounds)
    north = max(item[3] for item in bounds)
    corners = [transform.wgs84_to_local(lon, lat) for lon, lat in ((west, south), (west, north), (east, south), (east, north))]
    return min(item[0] for item in corners), min(item[1] for item in corners), max(item[0] for item in corners), max(item[1] for item in corners)


def preprocess_hgt(
    raw_path: Path,
    output_dir: Path,
    *,
    product: str,
    transform: CoordinateTransform | None = None,
    aoi_path: Path | None = None,
    local_bounds: tuple[float, float, float, float] | None = None,
    sample_spacing_m: float = 30.0,
    margin_m: float = 60.0,
    strict_dimensions: bool = False,
) -> dict[str, Any]:
    """Project a deterministic local grid and sample an HGT tile in WGS84."""

    if not raw_path.exists() or raw_path.stat().st_size == 0:
        raise FileNotFoundError(f"raw {product} DEM is absent; run the documented Earthdata acquisition first")
    if sample_spacing_m <= 0:
        raise ValueError("sample spacing must be positive")
    transform = transform or CoordinateTransform(ProjectConfig())
    canonical_product = str(product_source(product)["product"])
    expected_size = PRODUCT_RASTER_SIZES.get(canonical_product) if strict_dimensions else None
    tile_kwargs = {"product": canonical_product, "expected_size": expected_size}
    tile = HgtTile.from_archive(raw_path, **tile_kwargs) if raw_path.suffix.lower() == ".zip" else HgtTile.from_file(raw_path, **tile_kwargs)
    if local_bounds is None:
        if aoi_path is None:
            raise ValueError("aoi_path or local_bounds is required for real terrain preprocessing")
        local_bounds = _aoi_local_bounds(aoi_path, transform)
    west, south, east, north = local_bounds
    if aoi_path is not None and margin_m:
        west -= margin_m
        south -= margin_m
        east += margin_m
        north += margin_m
    if east <= west or north <= south:
        raise ValueError("local terrain bounds must have positive width and height")
    # Ceil semantics guarantee the final sample covers the requested edge,
    # including the explicit margin, instead of truncating east/north.
    columns = max(2, int(math.ceil((east - west) / sample_spacing_m)) + 1)
    rows = max(2, int(math.ceil((north - south) / sample_spacing_m)) + 1)
    values: list[tuple[float, ...]] = []
    nodata_count = 0
    interpolation_count = 0
    for row in range(rows):
        northing = south + row * sample_spacing_m
        samples: list[float] = []
        for column in range(columns):
            easting = west + column * sample_spacing_m
            lon, lat = transform.local_to_wgs84(easting, northing)
            try:
                samples.append(tile.sample(lon, lat))
                interpolation_count += 1
            except ValueError as exc:
                if "nodata" not in str(exc).lower():
                    raise
                nodata_count += 1
                raise ValueError(
                    f"{canonical_product} preprocessing encountered unresolved nodata at local grid "
                    f"row={row} column={column}; no interpolation policy is configured"
                ) from exc
        values.append(tuple(samples))
    valid_values = [value for row in values for value in row if value != float(tile.nodata)]
    if not valid_values:
        raise ValueError("processed HGT contains no valid elevation samples")
    world_base = math.floor(min(valid_values) - 2.0)
    field = HeightField(
        product=canonical_product,
        origin_east_m=west,
        origin_north_m=south,
        spacing_m=sample_spacing_m,
        values=tuple(values),
        nodata=float(tile.nodata),
        vertical_exaggeration=1.0,
        source_kind="real-nasa-raster",
        world_base_elevation_m=world_base,
        vertical_reference_policy="floor-minimum-minus-padding",
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_path = output_dir / "heightfield.json"
    field.write(processed_path)
    archive_sha256 = None
    if raw_path.suffix.lower() == ".zip":
        archive_sha256 = f"sha256:{hashlib.sha256(raw_path.read_bytes()).hexdigest()}"
    processed_sha256 = f"sha256:{hashlib.sha256(processed_path.read_bytes()).hexdigest()}"
    report = {
        "status": "pass" if nodata_count == 0 else "fail-nodata",
        "nodataPolicy": "reject-unresolved",
        "sourceKind": "real-nasa-raster",
        "product": canonical_product,
        "sourceHash": tile.source_hash,
        "archiveSha256": archive_sha256,
        "hgtPayloadSha256": tile.source_hash,
        "processedHeightfieldSha256": processed_sha256,
        "sourceCRS": "EPSG:4326",
        "localCRS": transform.config.projected_crs,
        "horizontalDatum": "WGS84",
        "verticalDatum": "EGM96",
        "nativeResolutionM": product_source(product)["resolutionM"],
        "processingResolutionM": sample_spacing_m,
        "processedSpacingM": sample_spacing_m,
        "minElevationM": field.min_elevation_m,
        "maxElevationM": field.max_elevation_m,
        "relativeMinElevationM": field.min_elevation_m - world_base,
        "relativeMaxElevationM": field.max_elevation_m - world_base,
        "nodataCount": nodata_count,
        "interpolatedCount": interpolation_count,
        "cropBoundsLocalM": {"westM": west, "southM": south, "eastM": east, "northM": north},
        "coverageBoundsLocalM": {
            "westM": west,
            "southM": south,
            "eastM": west + (columns - 1) * sample_spacing_m,
            "northM": south + (rows - 1) * sample_spacing_m,
        },
        "localOrigin": {"eastM": west, "northM": south},
        "verticalReference": {
            "sourceDatum": "EGM96",
            "worldBaseElevationM": world_base,
            "policy": "floor-minimum-minus-padding",
        },
        "processingVersion": "terrain-v0.2-real-hgt",
        "heightfield": "heightfield.json",
    }
    write_json(output_dir / "terrain-report.json", report)
    write_json(
        output_dir / "terrain-manifest.json",
        {
            **product_source(product),
            "sourceKind": "real-nasa-raster",
            "sourceHash": tile.source_hash,
            "archiveSha256": archive_sha256,
            "hgtPayloadSha256": tile.source_hash,
            "processedHeightfieldSha256": processed_sha256,
            "heightfield": "heightfield.json",
            "report": "terrain-report.json",
            "status": report["status"],
            "verticalReference": report["verticalReference"],
        },
    )
    return report


def preprocess_product(raw_path: Path, output_dir: Path, product: str, *, aoi_path: Path | None = None) -> dict[str, Any]:
    """Preprocess an acquired HGT/ZIP product without a GDAL dependency."""

    return preprocess_hgt(raw_path, output_dir, product=product, aoi_path=aoi_path, strict_dimensions=True)
