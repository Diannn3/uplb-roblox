from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.terrain.acquire import acquire_product
from tools.terrain.compare import choose_baseline, compare_products
from tools.terrain.preprocess import build_fixture_heightfield
from tools.terrain.sample import HeightField
from tools.terrain.validate import validate_heightfield
from tools.terrain.sources import PRODUCT_SOURCES


class TerrainPipelineTests(unittest.TestCase):
    def test_unresolved_nodata_fails_heightfield_validation(self) -> None:
        field = HeightField(
            product="NASADEM_HGT.001",
            origin_east_m=0.0,
            origin_north_m=0.0,
            spacing_m=30.0,
            values=((100.0, -32768.0), (101.0, 102.0)),
            nodata=-32768.0,
            source_kind="real-nasa-raster",
            world_base_elevation_m=90.0,
        )
        report = validate_heightfield(field)
        self.assertEqual(report["status"], "fail")
        self.assertIn("unresolved nodata", " ".join(report["errors"]))
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
            result = acquire_product("srtm", Path(directory), credentials_available=False)
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

    def test_real_baseline_selection_is_evidence_based_not_product_age(self) -> None:
        srtm = HeightField(product="SRTMGL1.003", origin_east_m=-10.0, origin_north_m=-10.0, spacing_m=10.0, values=((100.0, 100.2, 100.4), (100.1, 100.3, 100.5), (100.2, 100.4, 100.6)), source_kind="real-nasa-raster")
        nasadem = HeightField(product="NASADEM_HGT.001", origin_east_m=-10.0, origin_north_m=-10.0, spacing_m=10.0, values=((100.1, 100.3, 100.5), (100.2, 100.4, 100.6), (100.3, 100.5, 100.7)), source_kind="real-nasa-raster")
        comparison = compare_products(srtm, nasadem, {"oblation": (0.0, 0.0)})
        decision = choose_baseline(comparison)
        self.assertEqual(comparison["status"], "validated-raster")
        self.assertIn(decision["baseline"], {"SRTMGL1.003", "NASADEM_HGT.001"})
        self.assertTrue(decision["selectionReason"])
        self.assertIn("evidence", decision["selectionReason"].lower())


if __name__ == "__main__":
    unittest.main()
