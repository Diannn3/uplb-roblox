from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.worldgen.compile_scene import compile_scene
from tools.terrain.preprocess import build_fixture_heightfield
from tools.terrain.sample import HeightField


ROOT = Path(__file__).resolve().parents[2]


class SceneCompilerTests(unittest.TestCase):
    def test_scene_spec_is_deterministic_and_marks_fixture_terrain_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_dir = root / "fixture"
            build_fixture_heightfield("srtm", fixture_dir)
            first = compile_scene(
                root / "first",
                slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                terrain_path=fixture_dir / "heightfield.json",
                allow_fixture=True,
            )
            second = compile_scene(
                root / "second",
                slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                terrain_path=fixture_dir / "heightfield.json",
                allow_fixture=True,
            )
            self.assertEqual(first["sceneSpec"], second["sceneSpec"])
            self.assertEqual(first["sceneValidation"], second["sceneValidation"])
            self.assertEqual(first["sceneSpec"]["status"], "blocked-fixture-terrain")
            self.assertEqual(first["sceneSpec"]["terrain"]["sourceKind"], "synthetic-fixture")
            self.assertGreaterEqual(len(first["sceneSpec"]["objects"]), 95)
            self.assertTrue(first["sceneSpec"]["objects"][0]["geometry"]["coordinatesLocalMeters"])
            self.assertTrue((root / "first" / "scene-spec.json").exists())

    def test_scene_compiler_rejects_fixture_as_production_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_dir = Path(directory) / "fixture"
            build_fixture_heightfield("srtm", fixture_dir)
            with self.assertRaises(RuntimeError):
                compile_scene(
                    Path(directory),
                    slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                    terrain_path=fixture_dir / "heightfield.json",
                )

    def test_real_scene_preserves_terrain_acquisition_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = compile_scene(
                Path(directory) / "real",
                slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                terrain_path=ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json",
            )
            terrain = result["sceneSpec"]["terrain"]
            self.assertEqual(result["sceneSpec"]["status"], "ready")
            self.assertEqual(terrain["sourceKind"], "real-nasa-raster")
            for key in ("granule", "archiveSha256", "hgtPayloadSha256", "processedHeightfieldSha256", "retrievalTimestamp"):
                self.assertTrue(terrain[key], key)

    def test_real_scene_compiles_waterways_as_terrain_following_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = compile_scene(
                Path(directory) / "real",
                slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                terrain_path=ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json",
            )
            waterways = [item for item in result["sceneSpec"]["objects"] if item["role"] == "water" and item["geometry"]["type"] == "LineString"]
            self.assertTrue(waterways)
            self.assertTrue(all(item["geometry"]["centerlineCoordinatesLocalMeters3D"] for item in waterways))
            self.assertTrue(all(item["geometry"]["ribbonCoordinatesLocalMeters"] for item in waterways))

    def test_scene_compiler_rejects_unresolved_terrain_nodata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terrain = HeightField(
                product="NASADEM_HGT.001",
                origin_east_m=-1000.0,
                origin_north_m=-1000.0,
                spacing_m=30.0,
                values=((100.0, -32768.0), (101.0, 102.0)),
                nodata=-32768.0,
                source_kind="real-nasa-raster",
                world_base_elevation_m=90.0,
            )
            terrain_path = root / "heightfield.json"
            terrain.write(terrain_path)
            with self.assertRaisesRegex(ValueError, "unresolved nodata"):
                compile_scene(
                    root / "output",
                    slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                    terrain_path=terrain_path,
                )


if __name__ == "__main__":
    unittest.main()
