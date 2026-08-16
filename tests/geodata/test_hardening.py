from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.geodata.bootstrap import bootstrap
from tools.geodata.geometry import GeometryState, inspect_geometry, select_intersecting
from tools.geodata.identity import IdentityRegistry
from tools.geodata.models import CanonicalFeature
from tools.geodata.osm import ingest_osm_candidates
from tools.geodata.overture import OvertureProvider
from tools.geodata.conflate import conflate_buildings
from tools.geodata.pipeline import build
from tools.geodata.promote import promote
from tools.geodata.review import decide
from tools.geodata.schemas import validate_artifacts


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "geodata"


class HardeningTests(unittest.TestCase):
    def test_fixture_osm_ingest_emits_provider_candidates(self) -> None:
        result = ingest_osm_candidates(FIXTURES / "osm-small.json", accessed_at="2026-08-17")
        self.assertEqual(len(result.features), 4)
        self.assertTrue(all(feature.id.startswith("candidate:osm:") for feature in result.features))
        self.assertTrue(all(not feature.id.startswith("uplb:") for feature in result.features))
        relation = next(feature for feature in result.features if feature.external_ids["osm"] == "relation/400")
        self.assertEqual(relation.geometry["type"], "Polygon")
        self.assertEqual(len(relation.geometry["coordinates"]), 2)

    def test_identity_registry_preserves_named_identity_and_allocates_opaque_ids(self) -> None:
        registry = IdentityRegistry.load(FIXTURES / "identity-registry.json")
        existing = registry.resolve_or_allocate("building", "Baker Hall", {"osm": "way/999"}, promote=False)
        self.assertEqual(existing, "uplb:building:baker-hall")
        allocated = registry.resolve_or_allocate("building", "Unmapped Annex", {"osm": "way/999"}, promote=True)
        self.assertEqual(allocated, "uplb:building:bldg-000002")
        registry.update_external_id(existing, "osm", "way/1000")
        self.assertIn("way/1000", registry.entities[existing]["externalIds"]["osm"])

    def test_identity_registry_does_not_delete_canonical_when_candidate_disappears(self) -> None:
        registry = IdentityRegistry.load(FIXTURES / "identity-registry.json")
        registry.reconcile_candidates([])
        self.assertIn("uplb:building:baker-hall", registry.entities)

    def test_clean_bootstrap_uses_tracked_fixture_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = bootstrap(
                raw_path=FIXTURES / "osm-small.json",
                output_root=Path(directory),
                fetch=False,
                fixture_mode=True,
            )
            self.assertEqual(result["candidateCount"], 4)
            self.assertTrue((Path(directory) / "candidates" / "osm" / "features.geojson").exists())

    def test_geometry_inspection_repairs_only_safe_polygon_and_rejects_degenerate_line(self) -> None:
        payload = json.loads((FIXTURES / "invalid-geometries.geojson").read_text(encoding="utf-8"))
        polygon_result = inspect_geometry(payload["features"][0]["geometry"], source_hash="sha256:test")
        line_result = inspect_geometry(payload["features"][1]["geometry"], source_hash="sha256:test")
        self.assertIn(polygon_result.state, {GeometryState.REPAIRED_SAFE, GeometryState.NEEDS_REVIEW})
        self.assertEqual(line_result.state, GeometryState.REJECTED)
        self.assertEqual(line_result.reason, "degenerate-line")

    def test_slice_selection_uses_intersection_not_centroid(self) -> None:
        area = json.loads((FIXTURES / "vertical-slice.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"]
        crossing = {"type": "LineString", "coordinates": [[121.2395, 14.1602], [121.2420, 14.1602]]}
        outside = {"type": "Point", "coordinates": [121.2500, 14.1700]}
        features = [
            CanonicalFeature("candidate:osm:way/200", "walkway", "Crossing", crossing, ("source:test",), {"position": "medium"}, "candidate"),
            CanonicalFeature("candidate:osm:node/999", "poi", "Outside", outside, ("source:test",), {"position": "medium"}, "candidate"),
        ]
        selected = select_intersecting(features, area, buffer_m=0)
        self.assertEqual([feature.id for feature in selected], ["candidate:osm:way/200"])

    def test_overture_adapter_normalizes_fixture_without_internal_import(self) -> None:
        provider = OvertureProvider()
        candidates, source = provider.normalize_geojson(FIXTURES / "overture-small.geojson", release="2026-06-17.0")
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].id.startswith("candidate:overture:"))
        self.assertEqual(candidates[0].external_ids["overture"], "gERS:building:one")
        self.assertEqual(source["release"], "2026-06-17.0")

    def test_conflation_returns_projected_metrics_and_pending_review(self) -> None:
        osm = ingest_osm_candidates(FIXTURES / "osm-small.json").features
        overture, _ = OvertureProvider().normalize_geojson(FIXTURES / "overture-small.geojson", release="2026-06-17.0")
        reviews = conflate_buildings(osm, overture)
        baker = next(review for review in reviews if review.candidate_ids.get("osm") == "candidate:osm:way/100")
        self.assertEqual(baker.decision, "pending")
        self.assertGreaterEqual(baker.metrics["iou"], 0.5)
        self.assertIn("centroidDistanceM", baker.metrics)

    def test_pipeline_promotes_only_registry_entities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            result = build(
                osm_path=FIXTURES / "osm-small.json",
                output_dir=output_root / "canonical",
                fixture_path=ROOT / "research" / "fixtures" / "uplb_reference_points.geojson",
                accessed_at="2026-08-17",
                registry_path=ROOT / "data" / "canonical" / "identity-registry.json",
                area_path=ROOT / "data" / "areas" / "vertical-slice-v0.geojson",
                generated_path=output_root / "generated" / "CanonicalFeatures.lua",
            )
            self.assertEqual(result["canonicalCount"], 3)
            self.assertGreater(result["candidateCount"], result["canonicalCount"])
            canonical = json.loads((output_root / "canonical" / "features.geojson").read_text(encoding="utf-8"))
            self.assertEqual({feature["id"] for feature in canonical["features"]}, {
                "uplb:building:baker-hall", "uplb:landmark:oblation", "uplb:landmark:freedom-park"
            })

    def test_explicit_promotion_allocates_opaque_id_and_updates_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_root = root / "candidates"
            bootstrap(raw_path=FIXTURES / "osm-small.json", output_root=root, fixture_mode=True)
            registry_path = root / "identity-registry.json"
            shutil.copyfile(FIXTURES / "identity-registry.json", registry_path)
            canonical_path = root / "features.geojson"
            result = promote(
                "candidate:osm:way/200",
                candidate_root=candidate_root,
                registry_path=registry_path,
                canonical_path=canonical_path,
            )
            self.assertEqual(result["canonicalId"], "uplb:walkway:path-000001")
            self.assertIn(result["canonicalId"], json.loads(registry_path.read_text(encoding="utf-8"))["entities"])

    def test_review_accept_requires_local_candidate_and_promotes_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(
                osm_path=FIXTURES / "osm-small.json",
                output_dir=root / "canonical",
                fixture_path=ROOT / "research" / "fixtures" / "uplb_reference_points.geojson",
                accessed_at="2026-08-17",
                registry_path=ROOT / "data" / "canonical" / "identity-registry.json",
                area_path=ROOT / "data" / "areas" / "vertical-slice-v0.geojson",
                generated_path=root / "generated" / "CanonicalFeatures.lua",
                overture_path=FIXTURES / "overture-small.geojson",
                review_doc_path=root / "review.md",
            )
            review_path = root / "canonical" / "review-decisions.json"
            rows = json.loads(review_path.read_text(encoding="utf-8"))["decisions"]
            self.assertEqual(len(rows), 1)
            registry_path = root / "registry.json"
            shutil.copyfile(ROOT / "data" / "canonical" / "identity-registry.json", registry_path)
            result = decide(
                rows[0]["id"],
                "accept",
                review_path=review_path,
                registry_path=registry_path,
                canonical_path=root / "canonical" / "features.geojson",
                candidate_root=root / "candidates",
                reviewed_at="2026-08-17",
            )
            self.assertEqual(result["decision"], "accept")
            self.assertEqual(json.loads(review_path.read_text(encoding="utf-8"))["decisions"][0]["reviewStatus"], "reviewed")
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertIn("gERS:building:one", registry["entities"]["uplb:building:baker-hall"]["externalIds"]["overture"])

    def test_tracked_canonical_artifacts_validate(self) -> None:
        self.assertEqual(validate_artifacts(ROOT), [])


if __name__ == "__main__":
    unittest.main()
