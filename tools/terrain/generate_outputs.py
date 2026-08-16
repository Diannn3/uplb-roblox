"""Generate deterministic terrain comparison/fixture artifacts for the POC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from .compare import compare_products
from .preprocess import build_fixture_heightfield
from .preview import render_preview
from .sample import HeightField
from .sources import PRODUCT_SOURCES
from .validate import validate_heightfield
from tools.geodata.io import sha256, write_json
from tools.geodata.transform import CoordinateTransform


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPARISON = ROOT / "data" / "generated" / "terrain-comparison"
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "terrain-v0.1"
DEFAULT_SLICE = ROOT / "data" / "vertical-slices" / "v0.1" / "features.geojson"
DEFAULT_CONFIG = ROOT / "config" / "terrain.json"


def _hero_points(slice_path: Path) -> dict[str, tuple[float, float]]:
    transform = CoordinateTransform()
    payload = json.loads(slice_path.read_text(encoding="utf-8"))
    points: dict[str, tuple[float, float]] = {}
    aliases = {
        "UPLB Oblation": "oblation",
        "UPLB Freedom Park": "freedom-park",
        "Charles Fuller Baker Memorial Hall": "baker-hall",
        "Dioscoro L. Umali Hall": "dl-umali",
        "University Library and Knowledge Center": "main-library",
    }
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        if properties.get("worldgenRole") != "hero" or properties.get("name") not in aliases:
            continue
        point = shape(feature["geometry"]).representative_point()
        points[aliases[properties["name"]]] = transform.wgs84_to_local(float(point.x), float(point.y))[:2]
    if set(points) != set(aliases.values()):
        raise ValueError(f"slice hero points incomplete: {sorted(points)}")
    return points


def generate_outputs(
    comparison_dir: Path = DEFAULT_COMPARISON,
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    slice_path: Path = DEFAULT_SLICE,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    comparison_dir.mkdir(parents=True, exist_ok=True)
    srtm_dir, nasadem_dir = comparison_dir / "srtm", comparison_dir / "nasadem"
    srtm = build_fixture_heightfield("srtm", srtm_dir)
    nasadem = build_fixture_heightfield("nasadem", nasadem_dir)
    points = _hero_points(slice_path)
    comparison = compare_products(srtm, nasadem, points)
    comparison.update(
        {
            "comparisonRevision": "terrain-comparison-v0.1-fixture",
            "sourceStatus": "blocked-no-local-raster",
            "officialSources": {key: {"product": value["product"], "doi": value["doi"], "landingPage": value["landingPage"]} for key, value in PRODUCT_SOURCES.items()},
            "pointsCRS": "project-local metres (EPSG:32651 origin contract)",
        }
    )
    render_preview(srtm, comparison_dir / "srtm" / "preview.png")
    render_preview(nasadem, comparison_dir / "nasadem" / "preview.png")
    write_json(comparison_dir / "comparison.json", comparison)
    (comparison_dir / "README.md").write_text(
        "# Terrain comparison v0.1\n\n"
        "This directory contains deterministic synthetic fixture outputs only. NASADEM_HGT.001 and SRTMGL1.003 were not selected from these values; "
        "Earthdata acquisition remains blocked until a credentialed, current official route is available. No raster or credential is committed.\n",
        encoding="utf-8",
        newline="\n",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_heightfield = HeightField.read(srtm_dir / "heightfield.json")
    validation = validate_heightfield(fixture_heightfield)
    terrain_report = {
        "status": "blocked-no-local-raster",
        "sourceKind": fixture_heightfield.source_kind,
        "selectedDEM": None,
        "candidateProducts": [PRODUCT_SOURCES["srtm"]["product"], PRODUCT_SOURCES["nasadem"]["product"]],
        "resolutionM": 30,
        "sourceCRS": "EPSG:4326",
        "localCRS": "EPSG:32651",
        "horizontalDatum": "WGS84",
        "verticalDatum": "EGM96",
        "verticalExaggeration": 1.0,
        "minElevationM": fixture_heightfield.min_elevation_m,
        "maxElevationM": fixture_heightfield.max_elevation_m,
        "sampleSpacingM": fixture_heightfield.spacing_m,
        "nodataCount": 0,
        "interpolatedCount": 0,
        "localOrigin": {"eastM": fixture_heightfield.origin_east_m, "northM": fixture_heightfield.origin_north_m},
        "processingVersion": "terrain-v0.1-fixture",
        "validation": validation,
        "groundHeightApi": "tools.terrain.sample.HeightField.ground_height(local_east_m, local_north_m)",
        "knownLimitation": "Synthetic macro-slope fixture is not a NASA terrain comparison and cannot support a DEM baseline choice.",
    }
    fixture_heightfield.write(output_dir / "heightfield.json")
    render_preview(fixture_heightfield, output_dir / "preview.png")
    write_json(output_dir / "terrain-report.json", terrain_report)
    write_json(output_dir / "terrain-manifest.json", {"revision": "terrain-v0.1-fixture", "sourceHash": None, "sourceKind": fixture_heightfield.source_kind, "heightfield": "heightfield.json", "report": "terrain-report.json", "status": terrain_report["status"]})
    config = {
        "status": "blocked-no-local-raster",
        "baseline": None,
        "candidates": [PRODUCT_SOURCES["srtm"], PRODUCT_SOURCES["nasadem"]],
        "resolutionM": 30,
        "horizontalDatum": "WGS84",
        "verticalDatum": "EGM96",
        "selectionReason": "No NASA raster was acquired; do not choose a baseline from synthetic fixtures.",
        "sourceHash": None,
        "verticalExaggeration": 1.0,
        "terrainRevision": "terrain-v0.1-fixture",
    }
    write_json(config_path, config)
    return {"comparison": comparison, "terrainReport": terrain_report, "config": config}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = generate_outputs(args.comparison, args.output, slice_path=args.slice, config_path=args.config)
    print(json.dumps({"status": result["terrainReport"]["status"], "selectedDEM": result["terrainReport"]["selectedDEM"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
