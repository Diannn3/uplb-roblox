from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.blender.generate_greybox import generate_world


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "generated" / "greybox-v0.1"


class GreyboxTests(unittest.TestCase):
    def test_checked_in_world_manifest_has_required_heroes_and_traceable_objects(self) -> None:
        manifest = json.loads((OUTPUT / "world-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "superseded")
        self.assertEqual(manifest["supersededBy"], "data/generated/worldgen-v0.1/poc-gates.json")
        self.assertGreaterEqual(manifest["objectCount"], 50)
        self.assertEqual(manifest["determinism"], "pass")
        self.assertEqual(manifest["requiredHeroesMissing"], [])
        for obj in manifest["objects"]:
            self.assertTrue(obj["featureId"])
            self.assertTrue(obj["candidateId"].startswith("candidate:"))
            self.assertTrue(obj["sourceLifecycle"] in {"canonical", "candidate"})
            self.assertIn("InputHash", obj["metadata"])
            self.assertIn("TerrainRevision", obj["metadata"])
            if obj["worldgenRole"] == "context-building":
                self.assertIn("heightM", obj)
                self.assertIn("heightMethod", obj)
                self.assertIn("heightConfidence", obj)

    def test_greybox_generation_is_semantically_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = generate_world(Path(directory) / "first")
            second = generate_world(Path(directory) / "second")
            self.assertEqual(first["manifest"], second["manifest"])
            self.assertEqual(first["qa"], second["qa"])
            self.assertIn(first["manifest"]["status"], {"conditional-blender-unavailable", "blender-generated"})

    def test_previews_are_fixed_camera_outputs(self) -> None:
        expected = {"topdown.png", "oblation.png", "freedom-park.png", "baker-context.png", "dl-umali-context.png", "road-level.png"}
        self.assertTrue(expected.issubset({path.name for path in (OUTPUT / "previews").iterdir()}))


if __name__ == "__main__":
    unittest.main()
