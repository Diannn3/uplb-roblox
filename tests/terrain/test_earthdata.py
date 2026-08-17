from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.terrain.acquire import acquire_product, search_product


class FakeEarthaccess:
    def __init__(self) -> None:
        self.login_calls = 0
        self.search_kwargs = None

    def login(self):
        self.login_calls += 1
        return object()

    def search_data(self, **kwargs):
        self.search_kwargs = kwargs
        return [
            {
                "conceptId": "G123",
                "shortName": kwargs["short_name"],
                "version": kwargs["version"],
                "bbox": [121.0, 14.0, 122.0, 15.0],
                "filename": "N14E121.hgt.zip",
            }
        ]

    def download(self, results, output):
        destination = Path(output) / results[0]["filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"verified test payload")
        return [destination]


class FailingEarthaccess(FakeEarthaccess):
    def download(self, results, output):
        destination = Path(output) / results[0]["filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"partial payload")
        raise RuntimeError("simulated download failure")


class EarthdataTests(unittest.TestCase):
    def test_search_derives_aoi_and_pins_product_identity(self) -> None:
        fake = FakeEarthaccess()
        result = search_product(
            "srtm",
            Path("data/vertical-slices/v0.1/area.geojson"),
            earthaccess_client=fake,
        )
        self.assertEqual(result["status"], "search-passed")
        self.assertEqual(result["product"], "SRTMGL1.003")
        self.assertEqual(result["granules"][0]["conceptId"], "G123")
        self.assertEqual(fake.search_kwargs["short_name"], "SRTMGL1")
        self.assertEqual(fake.search_kwargs["version"], "003")
        self.assertEqual(fake.search_kwargs["bounding_box"], [121.238, 14.158, 121.2465, 14.1685])

    def test_authenticated_download_records_hashes_without_secrets(self) -> None:
        fake = FakeEarthaccess()
        with tempfile.TemporaryDirectory() as directory:
            result = acquire_product(
                "srtm",
                Path(directory),
                earthaccess_client=fake,
                credentials_available=True,
                aoi_path=Path("data/vertical-slices/v0.1/area.geojson"),
            )
            self.assertEqual(result["status"], "downloaded")
            self.assertEqual(fake.login_calls, 1)
            self.assertTrue(result["manifest"])
            self.assertTrue(result["manifest"]["files"][0]["sha256"].startswith("sha256:"))
            self.assertNotIn("password", str(result).lower())

    def test_failed_download_removes_partial_nonzero_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = acquire_product(
                "srtm",
                Path(directory),
                earthaccess_client=FailingEarthaccess(),
                credentials_available=True,
                aoi_path=Path("data/vertical-slices/v0.1/area.geojson"),
            )
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(list(Path(directory).glob("**/*")))


if __name__ == "__main__":
    unittest.main()
