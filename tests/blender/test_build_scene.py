from __future__ import annotations

import unittest

from tools.blender.build_scene import (
    COLLECTIONS_BY_ROLE,
    RENDER_FILENAMES,
    build_custom_properties,
    _flat_polygon_mesh,
    _polygon_loops,
    terrain_faces,
    validate_structural_snapshot,
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
        self.assertEqual(set(properties), {"FeatureId", "FeatureName", "SemanticObjectId", "CandidateId", "SourceLifecycle", "WorldgenRole", "DetailTier", "CanonicalRevision", "TerrainRevision", "SceneSpecHash", "GeneratorVersion", "InputHash", "GeometryConfidence", "HeightConfidence", "ProxyCenterEastM", "ProxyCenterNorthM", "ProxyWidthM", "ProxyDepthM", "ProxyYawDegrees", "ProxySource"})

    def test_all_scene_roles_have_diagnostic_collections(self) -> None:
        for role in {"hero", "context-building", "road", "walkway", "water", "green-space", "landmark-placeholder"}:
            self.assertIn(role, COLLECTIONS_BY_ROLE)

    def test_real_render_filenames_match_the_visual_gate_contract(self) -> None:
        self.assertEqual(
            set(RENDER_FILENAMES.values()),
            {"topdown.png", "oblation.png", "freedom-park.png", "baker-context.png", "dl-umali-context.png", "road-level.png", "library-context.png"},
        )

    def test_polygon_loops_accept_compiled_local_meter_coordinates(self) -> None:
        geometry = {
            "type": "Polygon",
            "coordinatesLocalMeters": [[[1.0, 2.0], [3.0, 2.0], [3.0, 4.0], [1.0, 2.0]]],
        }
        self.assertEqual(_polygon_loops(geometry), [[[[1.0, 2.0], [3.0, 2.0], [3.0, 4.0], [1.0, 2.0]]]])

    def test_structural_snapshot_passes_only_when_real_checks_are_clean(self) -> None:
        properties = {
            "FeatureId": "uplb:hero:test",
            "FeatureName": "UPLB Oblation",
            "SemanticObjectId": "scene:uplb:hero:test",
            "WorldgenRole": "hero",
            "SceneSpecHash": "sha256:scene",
            "GeneratorVersion": "blender-v0.2",
            "InputHash": "sha256:input",
            "GeometryConfidence": "verified",
            "HeightConfidence": "verified",
        }
        result = validate_structural_snapshot(
            [
                {
                    "name": "HERO_UPLB_Oblation",
                    "type": "MESH",
                    "location": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                    "dimensions": [2.0, 2.0, 4.0],
                    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    "faceAreas": [0.5],
                    "properties": properties,
                }
            ],
            present_collections={"Terrain", "Buildings", "Roads", "Walkways", "Water", "GreenSpace", "Landmarks", "Debug"},
            present_cameras=set(RENDER_FILENAMES),
            render_paths=list(RENDER_FILENAMES.values()),
        )
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["missingRequiredHeroes"])

    def test_structural_snapshot_detects_bad_scale_vertex_face_and_metadata(self) -> None:
        result = validate_structural_snapshot(
            [
                {
                    "name": "bad",
                    "type": "MESH",
                    "location": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "scale": [-1.0, 1.0, float("nan")],
                    "dimensions": [1.0, 1.0, 1.0],
                    "vertices": [[0.0, 0.0, float("inf")]],
                    "faceAreas": [0.0],
                    "properties": {"FeatureId": "uplb:bad", "SemanticObjectId": "scene:bad"},
                }
            ],
            present_collections=set(),
            present_cameras=set(),
            render_paths=[],
        )
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["negativeScales"])
        self.assertTrue(result["nonFiniteScales"])
        self.assertTrue(result["nonFiniteMeshVertices"])
        self.assertTrue(result["degenerateFaces"])
        self.assertTrue(result["missingMetadata"])

    def test_flat_polygon_preserves_simple_polygon(self) -> None:
        vertices, faces = _flat_polygon_mesh(
            {"type": "Polygon", "coordinatesLocalMeters": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
            2.0,
        )
        self.assertEqual(len(vertices), 4)
        self.assertEqual(len(faces), 2)

    def test_flat_polygon_preserves_one_hole(self) -> None:
        geometry = {
            "type": "Polygon",
            "coordinatesLocalMeters": [
                [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                [[3, 3], [3, 7], [7, 7], [7, 3], [3, 3]],
            ],
        }
        vertices, faces = _flat_polygon_mesh(geometry, 2.0)
        self.assertEqual(len(vertices), 8)
        self.assertGreaterEqual(len(faces), 4)
        area = sum(abs((vertices[face[1]][0] - vertices[face[0]][0]) * (vertices[face[2]][1] - vertices[face[0]][1]) - (vertices[face[1]][1] - vertices[face[0]][1]) * (vertices[face[2]][0] - vertices[face[0]][0])) / 2 for face in faces)
        self.assertAlmostEqual(area, 84.0)

    def test_flat_polygon_preserves_multipolygon_and_multipolygon_hole(self) -> None:
        geometry = {
            "type": "MultiPolygon",
            "coordinatesLocalMeters": [
                [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
                [
                    [[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]],
                    [[13, 3], [13, 7], [17, 7], [17, 3], [13, 3]],
                ],
            ],
        }
        first = _flat_polygon_mesh(geometry, 2.0)
        second = _flat_polygon_mesh(geometry, 2.0)
        self.assertEqual(first, second)
        vertices, faces = first
        self.assertEqual(len(vertices), 12)
        area = sum(abs((vertices[face[1]][0] - vertices[face[0]][0]) * (vertices[face[2]][1] - vertices[face[0]][1]) - (vertices[face[1]][1] - vertices[face[0]][1]) * (vertices[face[2]][0] - vertices[face[0]][0])) / 2 for face in faces)
        self.assertAlmostEqual(area, 100.0)


if __name__ == "__main__":
    unittest.main()
