from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.geodata.conflate import conflate_buildings
from tools.geodata.generate_luau import generate_luau
from tools.geodata.io import read_json, sha256, write_json
from tools.geodata.models import CanonicalFeature, SourceRecord
from tools.geodata.osm import ingest_osm
from tools.geodata.overture_fallback import probe_cli, probe_direct
from tools.geodata.pipeline import select_vertical_slice
from tools.geodata.schemas import validate_schema_documents
from tools.geodata.transform import CoordinateTransform, ProjectConfig, RobloxPoint
from tools.geodata.validation import validate_features


ROOT = Path(__file__).resolve().parents[2]
OSM_PATH = ROOT / "tests" / "fixtures" / "geodata" / "osm-small.json"


class FoundationTests(unittest.TestCase):
    def test_transform_roundtrip_and_axis_convention(self) -> None:
        transform = CoordinateTransform()
        point = transform.wgs84_to_roblox(121.24173, 14.16128, elevation_m=12.0)
        self.assertAlmostEqual(point.x, 58.36, delta=0.8)
        self.assertGreater(point.y, 0)
        self.assertGreater(point.z, 0)
        lon, lat, elevation = transform.roblox_to_wgs84(point)
        self.assertAlmostEqual(lon, 121.24173, places=7)
        self.assertAlmostEqual(lat, 14.16128, places=7)
        self.assertAlmostEqual(elevation, 12.0, places=7)

    def test_transform_scale_is_explicit(self) -> None:
        transform = CoordinateTransform(ProjectConfig(meters_per_stud=0.5))
        point = transform.local_to_roblox(2.0, 3.0, 4.0)
        self.assertEqual(point, RobloxPoint(4.0, 8.0, -6.0))

    def test_osm_ingest_is_pinned_and_finds_baker(self) -> None:
        result = ingest_osm(OSM_PATH)
        self.assertEqual(len(result.features), 4)
        self.assertEqual(result.source.content_hash, f"sha256:{sha256(OSM_PATH)}")
        baker = next(feature for feature in result.features if feature.id == "uplb:building:baker-hall")
        self.assertEqual(baker.external_ids["osm"], "way/100")
        self.assertEqual(baker.properties["levels"], 2.0)
        self.assertEqual(result.skipped_elements, 0)

    def test_vertical_slice_keeps_required_landmarks(self) -> None:
        features = [
            CanonicalFeature("uplb:building:baker-hall", "building", "Baker Hall", {"type": "Point", "coordinates": [121.24, 14.16]}, ("source:test",), {"position": "medium"}, "reference-only"),
            CanonicalFeature("uplb:landmark:oblation", "landmark", "Oblation", {"type": "Point", "coordinates": [121.24155, 14.165]}, ("source:test",), {"position": "medium"}, "reference-only"),
            CanonicalFeature("uplb:landmark:freedom-park", "landmark", "Freedom Park", {"type": "Point", "coordinates": [121.24173, 14.16128]}, ("source:test",), {"position": "medium"}, "reference-only"),
        ]
        selected = {feature.id for feature in select_vertical_slice(features)}
        self.assertEqual(
            selected,
            {"uplb:building:baker-hall", "uplb:landmark:oblation", "uplb:landmark:freedom-park"},
        )

    def test_conflation_emits_review_without_merging(self) -> None:
        canonical = CanonicalFeature(
            "uplb:building:baker-hall",
            "building",
            "Charles Fuller Baker Memorial Hall",
            {"type": "Polygon", "coordinates": [[[121.24, 14.16], [121.241, 14.16], [121.241, 14.161], [121.24, 14.16]]]},
            ("source:osm",),
            {"position": "medium"},
            "needs-site-verification",
        )
        candidate = CanonicalFeature(
            "uplb:building:overture-123",
            "building",
            "Baker Hall",
            {"type": "Polygon", "coordinates": [[[121.2401, 14.1601], [121.2409, 14.1601], [121.2409, 14.1609], [121.2401, 14.1601]]]},
            ("source:overture",),
            {"position": "medium"},
            "needs-conflation-review",
        )
        reviews = conflate_buildings([canonical], [candidate])
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].decision, "pending")
        self.assertEqual(reviews[0].canonical_id, canonical.id)

    def test_validation_fails_unknown_provenance(self) -> None:
        feature = CanonicalFeature("uplb:test:one", "poi", "Test", None, ("source:missing",), {"position": "unknown"}, "reference-only")
        source = SourceRecord("source:known", "Test", "https://example.invalid", "2026-08-17", "open-attribution-required", ("test",))
        report = validate_features([feature], [source], {})
        self.assertEqual(report.decision, "fail")
        self.assertTrue(any(check["name"] == "provenance-completeness" and check["status"] == "fail" for check in report.checks))

    def test_generated_luau_is_deterministic_and_uses_roblox_axes(self) -> None:
        feature = CanonicalFeature("uplb:landmark:test", "landmark", "Test", {"type": "Point", "coordinates": [121.24155, 14.165]}, ("source:test",), {"position": "medium"}, "reference-only")
        transform = CoordinateTransform()
        first = generate_luau([feature], transform, "abc123")
        second = generate_luau([feature], transform, "abc123")
        self.assertEqual(first, second)
        self.assertIn('SOURCE_HASH = "abc123"', first)
        self.assertIn('FEATURE_COUNT = 1', first)
        self.assertIn('x = 0', first)
        self.assertIn('z = 0', first)

    def test_json_writer_is_utf8_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "value.json"
            write_json(path, {"z": "Los Baños", "a": 1})
            self.assertEqual(read_json(path), {"z": "Los Baños", "a": 1})
            self.assertTrue(path.read_bytes().startswith(b"{\n  \"a\""))

    def test_overture_probes_fail_closed_without_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cli_result = probe_cli("missing-overturemaps", (121.225, 14.145, 121.265, 14.185), Path(directory) / "out.geojson", 1)
            self.assertEqual(cli_result["status"], "blocked")
            direct_result = probe_direct("missing-python", "2026-06-17.0", (121.225, 14.145, 121.265, 14.185), 1)
            self.assertIn(direct_result["status"], {"blocked", "timeout"})

    def test_production_schema_bundle_is_complete(self) -> None:
        self.assertEqual(validate_schema_documents(), [])


if __name__ == "__main__":
    unittest.main()
