from __future__ import annotations

import unittest

from tools.blender.build_scene import (
    COLLECTIONS_BY_ROLE,
    build_custom_properties,
    terrain_faces,
)


class BlenderBuilderContractTests(unittest.TestCase):
    def test_terrain_faces_have_deterministic_triangle_order(self) -> None:
        self.assertEqual(terrain_faces(2, 3), [(0, 1, 3), (1, 4, 3), (1, 2, 4), (2, 5, 4)])

    def test_custom_properties_are_traceable_to_scene_spec(self) -> None:
        properties = build_custom_properties(
            {
                "featureId": "uplb:building:test",
                "candidateId": "candidate:osm:way/1",
                "sourceLifecycle": "candidate",
                "role": "context-building",
                "metadata": {"canonicalRevision": "rev-c", "terrainRevision": "rev-t", "inputHash": "hash-in"},
                "height": {"confidence": "placeholder"},
            },
            scene_spec_hash="hash-scene",
            generator_version="blender-v0.2",
        )
        self.assertEqual(properties["FeatureId"], "uplb:building:test")
        self.assertEqual(properties["SceneSpecHash"], "hash-scene")
        self.assertEqual(properties["GeneratorVersion"], "blender-v0.2")
        self.assertEqual(properties["HeightConfidence"], "placeholder")
        self.assertEqual(set(properties), {"FeatureId", "CandidateId", "SourceLifecycle", "WorldgenRole", "DetailTier", "CanonicalRevision", "TerrainRevision", "SceneSpecHash", "GeneratorVersion", "InputHash", "GeometryConfidence", "HeightConfidence"})

    def test_all_scene_roles_have_diagnostic_collections(self) -> None:
        for role in {"hero", "context-building", "road", "walkway", "water", "green-space", "landmark-placeholder"}:
            self.assertIn(role, COLLECTIONS_BY_ROLE)


if __name__ == "__main__":
    unittest.main()
