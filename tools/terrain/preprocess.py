"""DEM preprocessing and explicit deterministic fixture harness."""

from __future__ import annotations

import json
from pathlib import Path

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
    field = HeightField(product=str(source["product"]), origin_east_m=-600.0, origin_north_m=-1000.0, spacing_m=spacing, values=values, source_kind="synthetic-fixture", vertical_exaggeration=1.0)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        field.write(output_dir / "heightfield.json")
        manifest = {
            **source,
            "sourceKind": "synthetic-fixture",
            "sourceHash": None,
            "processing": {"targetCRS": "EPSG:32651", "localCoordinates": True, "verticalExaggeration": 1.0, "crop": "fixture-only"},
            "heightfield": "heightfield.json",
            "status": "fixture-only",
        }
        (output_dir / "terrain-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return field


def preprocess_product(raw_path: Path, output_dir: Path, product: str) -> dict[str, str]:
    """Fail closed until a supported raster reader and verified raw raster exist."""

    if not raw_path.exists() or raw_path.stat().st_size == 0:
        raise FileNotFoundError(f"raw {product} DEM is absent; run the documented Earthdata acquisition first")
    raise RuntimeError("raster preprocessing requires the project-approved GDAL/raster reader; no implicit fallback is allowed")
