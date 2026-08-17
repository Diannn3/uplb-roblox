from __future__ import annotations

import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from tools.terrain.hgt import HgtTile


class HgtReaderTests(unittest.TestCase):
    def _write_tile(self, path: Path) -> None:
        values = (100, 110, 120, 90, 100, 110, 80, 90, -32768)
        path.write_bytes(b"".join(struct.pack(">h", value) for value in values))

    def test_reads_big_endian_tile_and_bilinearly_samples_nodata_safe_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "N14E121.hgt"
            self._write_tile(path)
            tile = HgtTile.from_file(path, product="SRTMGL1.003")

            self.assertEqual(tile.size, 3)
            self.assertIsInstance(tile.values, np.ndarray)
            self.assertEqual(tile.values.shape, (3, 3))
            self.assertEqual(tile.bounds, (121.0, 14.0, 122.0, 15.0))
            self.assertEqual(tile.sample(121.0, 15.0), 100.0)
            self.assertAlmostEqual(tile.sample(121.25, 14.75), 100.0)
            with self.assertRaises(ValueError):
                tile.sample(121.75, 14.25)

    def test_reads_hgt_from_zip_without_spreading_archive_logic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hgt = root / "N14E121.hgt"
            self._write_tile(hgt)
            archive = root / "tile.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.write(hgt, hgt.name)
            tile = HgtTile.from_archive(archive, product="NASADEM_HGT.001")
            self.assertEqual(tile.product, "NASADEM_HGT.001")
            self.assertEqual(tile.source_kind, "real-nasa-raster")

    def test_strict_production_dimension_validation_rejects_fixture_grid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "N14E121.hgt"
            self._write_tile(path)
            with self.assertRaisesRegex(ValueError, "expected 3601x3601"):
                HgtTile.from_file(path, product="SRTMGL1.003", expected_size=3601)


if __name__ == "__main__":
    unittest.main()
