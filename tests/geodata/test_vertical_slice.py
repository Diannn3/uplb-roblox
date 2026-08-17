from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.geodata.vertical_slice import build_vertical_slice


ROOT = Path(__file__).resolve().parents[2]
SLICE = ROOT / "data" / "vertical-slices" / "v0.1"


class VerticalSliceTests(unittest.TestCase):
    def test_checked_in_slice_has_required_contract_files(self) -> None:
        expected = {"area.geojson", "features.geojson", "selection.json", "canonical-bindings.json", "source-manifest.json", "validation-report.json", "README.md"}
        self.assertTrue(expected.issubset({path.name for path in SLICE.iterdir()}))

    def test_slice_is_bounded_traceable_and_preserves_candidate_lifecycle(self) -> None:
        selection = json.loads((SLICE / "selection.json").read_text(encoding="utf-8"))
        payload = json.loads((SLICE / "features.geojson").read_text(encoding="utf-8"))
        self.assertGreaterEqual(selection["selectedFeatureCount"], 50)
        self.assertLessEqual(selection["selectedFeatureCount"], 150)
        self.assertEqual(len(payload["features"]), selection["selectedFeatureCount"])
        self.assertEqual(selection["reviewVersion"], "v1")
        self.assertTrue(selection["candidateSourceHash"].startswith("sha256:"))
        self.assertEqual(selection["requiredHeroesMissing"], [])
        hero_names = {feature["properties"]["name"] for feature in payload["features"] if feature["properties"]["worldgenRole"] == "hero"}
        self.assertTrue({"UPLB Oblation", "UPLB Freedom Park", "Charles Fuller Baker Memorial Hall"}.issubset(hero_names))
        for feature in payload["features"]:
            properties = feature["properties"]
            self.assertIn(properties["worldgenRole"], {"hero", "context-building", "road", "walkway", "water", "green-space", "landmark-placeholder", "exclude"})
            self.assertIn(properties["detailTier"], {0, 1, 2, 3})
            self.assertTrue(properties["candidateId"].startswith("candidate:"))
            self.assertTrue(properties["provenance"])
            if properties["sourceLifecycle"] == "candidate":
                self.assertIsNone(properties.get("canonicalId"))

    def test_slice_contains_bounded_candidate_green_space_context(self) -> None:
        selection = json.loads((SLICE / "selection.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(selection["roleCounts"]["green-space"], 1)
        self.assertLessEqual(selection["selectedFeatureCount"], 120)

    def test_slice_generation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = build_vertical_slice(Path(directory) / "first")
            second = build_vertical_slice(Path(directory) / "second")
            self.assertEqual(first["selection"], second["selection"])
            first_features = json.loads((Path(directory) / "first" / "features.geojson").read_text(encoding="utf-8"))
            second_features = json.loads((Path(directory) / "second" / "features.geojson").read_text(encoding="utf-8"))
            self.assertEqual(first_features, second_features)


if __name__ == "__main__":
    unittest.main()
