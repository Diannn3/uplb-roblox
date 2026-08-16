from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.terrain.acquire import acquire_product
from tools.terrain.compare import compare_products
from tools.terrain.preprocess import build_fixture_heightfield
from tools.terrain.sample import HeightField
from tools.terrain.sources import PRODUCT_SOURCES


class TerrainPipelineTests(unittest.TestCase):
    def test_official_products_have_current_metadata_and_shared_datum_contract(self) -> None:
        self.assertEqual(PRODUCT_SOURCES["srtm"]["product"], "SRTMGL1.003")
        self.assertEqual(PRODUCT_SOURCES["nasadem"]["product"], "NASADEM_HGT.001")
        for source in PRODUCT_SOURCES.values():
            self.assertEqual(source["horizontalCRS"], "EPSG:4326")
            self.assertEqual(source["horizontalDatum"], "WGS84")
            self.assertEqual(source["verticalDatum"], "EGM96")
            self.assertEqual(source["resolutionM"], 30)
            self.assertIn("Earthdata", source["acquisitionRoute"])
            self.assertIn("doi", source)

    def test_acquisition_fails_closed_without_credentials_and_cleans_zero_byte_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = acquire_product("srtm", Path(directory))
            self.assertEqual(result["status"], "blocked")
            self.assertIn("Earthdata Login", result["diagnostic"])
            self.assertFalse(list(Path(directory).glob("**/*")))

    def test_fixture_sampling_and_comparison_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            srtm = build_fixture_heightfield("srtm", root / "srtm")
            nasadem = build_fixture_heightfield("nasadem", root / "nasadem")
            self.assertIsInstance(srtm, HeightField)
            self.assertEqual(srtm.ground_height(0.0, 0.0), srtm.ground_height(0.0, 0.0))
            points = {"oblation": (0.0, 0.0), "freedom-park": (30.0, 30.0), "baker-hall": (60.0, 0.0), "dl-umali": (0.0, 60.0), "main-library": (60.0, 60.0)}
            first = compare_products(srtm, nasadem, points)
            second = compare_products(srtm, nasadem, points)
            self.assertEqual(first, second)
            self.assertEqual(set(first["samples"]), set(points))
            self.assertEqual(first["status"], "fixture-only")
            self.assertFalse(first["baselineSelected"])


if __name__ == "__main__":
    unittest.main()
