from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.terrain.generate_outputs import generate_outputs


ROOT = Path(__file__).resolve().parents[2]


class RealComparisonTests(unittest.TestCase):
    def test_acquired_hgt_products_use_identical_processing_and_select_real_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            for key, offset in (("srtm", 0), ("nasadem", 1)):
                product_dir = raw / key
                product_dir.mkdir(parents=True)
                values = [100 + offset + index for index in range(9)]
                (product_dir / "N14E121.hgt").write_bytes(b"".join(struct.pack(">h", value) for value in values))
            result = generate_outputs(
                root / "comparison",
                root / "terrain",
                slice_path=ROOT / "data" / "vertical-slices" / "v0.1" / "features.geojson",
                config_path=root / "terrain-config.json",
                raw_root=raw,
            )
            self.assertEqual(result["comparison"]["sourceStatus"], "validated-raster")
            self.assertTrue(result["config"]["baseline"])
            self.assertEqual(result["terrainReport"]["sourceKind"], "real-nasa-raster")
            self.assertTrue((root / "comparison" / "srtm-report.json").exists())
            self.assertTrue((root / "comparison" / "nasadem-report.json").exists())


if __name__ == "__main__":
    unittest.main()
