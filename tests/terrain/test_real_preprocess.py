from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.geodata.transform import CoordinateTransform, ProjectConfig
from tools.terrain.preprocess import preprocess_hgt
from tools.terrain.sample import HeightField


class RealPreprocessTests(unittest.TestCase):
    def test_inverse_projects_local_grid_and_samples_real_hgt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "N14E121.hgt"
            raw.write_bytes(b"".join(struct.pack(">h", value) for value in (100, 101, 102, 99, 100, 101, 98, 99, 100)))
            transform = CoordinateTransform(ProjectConfig(origin_lon=121.5, origin_lat=14.5))
            result = preprocess_hgt(
                raw,
                root / "output",
                product="SRTMGL1.003",
                transform=transform,
                local_bounds=(-20.0, -20.0, 20.0, 20.0),
                sample_spacing_m=20.0,
            )
            field = HeightField.read(root / "output" / "heightfield.json")
            self.assertEqual(result["sourceKind"], "real-nasa-raster")
            self.assertEqual(field.source_kind, "real-nasa-raster")
            self.assertGreaterEqual(field.rows, 2)
            self.assertGreaterEqual(field.columns, 2)
            self.assertEqual(result["interpolatedCount"], field.rows * field.columns)


if __name__ == "__main__":
    unittest.main()
