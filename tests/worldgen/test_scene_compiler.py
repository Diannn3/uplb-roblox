from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.worldgen.compile_scene import compile_scene


ROOT = Path(__file__).resolve().parents[2]


class SceneCompilerTests(unittest.TestCase):
    def test_scene_spec_is_deterministic_and_marks_fixture_terrain_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = compile_scene(
                root / "first",
                slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                terrain_path=ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json",
                allow_fixture=True,
            )
            second = compile_scene(
                root / "second",
                slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                terrain_path=ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json",
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
            with self.assertRaises(RuntimeError):
                compile_scene(
                    Path(directory),
                    slice_dir=ROOT / "data" / "vertical-slices" / "v0.1",
                    terrain_path=ROOT / "data" / "generated" / "terrain-v0.1" / "heightfield.json",
                )


if __name__ == "__main__":
    unittest.main()
