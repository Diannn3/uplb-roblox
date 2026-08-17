from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.terrain.generate_outputs import generate_outputs


ROOT = Path(__file__).resolve().parents[2]


class RealComparisonTests(unittest.TestCase):
    def test_baseline_decision_records_all_metrics_and_prefers_consistent_product(self) -> None:
        from tools.terrain.compare import choose_baseline

        comparison = {
            "status": "validated-raster",
            "coverage": {
                "srtm": {"westM": 0, "southM": 0, "eastM": 10, "northM": 10},
                "nasadem": {"westM": 0, "southM": 0, "eastM": 10, "northM": 10},
            },
            "metrics": {
                "srtm": {"nodataCount": 0, "maxAdjacentDeltaM": 11, "p95AdjacentDeltaM": 6, "spikeCount": 20},
                "nasadem": {"nodataCount": 0, "maxAdjacentDeltaM": 10, "p95AdjacentDeltaM": 5, "spikeCount": 10},
            },
        }
        decision = choose_baseline(comparison)
        self.assertEqual(decision["baseline"], "NASADEM_HGT.001")
        self.assertEqual(decision["policyVersion"], "terrain-baseline-v0.2")
        self.assertEqual(
            decision["metricsConsidered"],
            ["nodataCount", "maxAdjacentDeltaM", "p95AdjacentDeltaM", "spikeCount", "coverageEquality"],
        )
        self.assertTrue(decision["decisionBasis"]["coverageEqual"])
        self.assertEqual(decision["decisionBasis"]["scores"]["nasadem"], [0, 10.0, 5.0, 10])

    def test_baseline_decision_fails_closed_when_coverage_differs(self) -> None:
        from tools.terrain.compare import choose_baseline

        comparison = {
            "status": "validated-raster",
            "coverage": {
                "srtm": {"westM": 0, "southM": 0, "eastM": 10, "northM": 10},
                "nasadem": {"westM": 0, "southM": 0, "eastM": 11, "northM": 10},
            },
            "metrics": {"srtm": {}, "nasadem": {}},
        }
        decision = choose_baseline(comparison)
        self.assertIsNone(decision["baseline"])
        self.assertFalse(decision["decisionBasis"]["coverageEqual"])
        self.assertIn("coverage", decision["selectionReason"].lower())

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

    def test_real_comparison_records_regular_grid_continuity_and_spike_metrics(self) -> None:
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
            comparison = result["comparison"]
            self.assertEqual(comparison["artifactBehavior"], "real-raster-compared")
            self.assertGreater(comparison["regularGrid"]["validCount"], 0)
            self.assertIn("p95AdjacentDeltaM", comparison["metrics"]["srtm"])
            self.assertIn("spikeCount", comparison["metrics"]["nasadem"])
            self.assertTrue(comparison["baselineSelected"])

    def test_real_config_retains_archive_granule_and_processed_hashes(self) -> None:
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
            config = result["config"]
            self.assertEqual(config["status"], "ready-real-terrain")
            for key in ("baseline", "product", "version", "archiveSha256", "hgtPayloadSha256", "processedHeightfieldSha256", "granule", "retrievalTimestamp", "coverageBoundsLocalM", "nativeResolutionM", "processedSpacingM", "horizontalDatum", "verticalDatum", "selectionReason", "terrainRevision"):
                self.assertIn(key, config)
            self.assertTrue(config["processedHeightfieldSha256"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
