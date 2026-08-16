from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.geodata.overture_check_updates import check_updates
from tools.geodata.phase_gate import build_gate
from tools.geodata.review import decide_priority, modify_priority
from tools.geodata.review_approval import freeze_review_v1
from tools.geodata.review_priority import build_priority_package, priority_score
from tools.geodata.schemas import validate_artifacts
from tools.geodata.models import ProviderCandidate


ROOT = Path(__file__).resolve().parents[2]


class PhaseOneClosureTests(unittest.TestCase):
    def test_closure_exposes_poc_and_campus_gates(self) -> None:
        report = build_gate()
        payload = report.to_dict()
        self.assertEqual(report.engineering_gate, "pass")
        self.assertEqual(report.canonical_identity_gate, "pass")
        self.assertEqual(report.geometry_gate, "pass")
        self.assertEqual(report.reproducibility_gate, "pass")
        self.assertEqual(report.human_review_gate, "pass")
        self.assertEqual(report.dem_rights_gate, "pass")
        self.assertEqual(report.overture_comparison_gate, "blocked")
        self.assertEqual(payload["decision"], "PASS_FOR_POC")
        self.assertEqual(payload["hardBlockers"], [])
        self.assertTrue(payload["deferredEnhancements"])
        self.assertTrue(payload["campusWideBlockers"])
        self.assertTrue(report.worldgen_ready)
        self.assertFalse(report.campus_wide_production_ready)
        self.assertTrue(payload["worldgenReady"])

    def test_priority_package_has_required_quota_and_heroes(self) -> None:
        package = json.loads((ROOT / "data" / "reviews" / "vertical-slice-review.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(package["counts"].values()), 25)
        self.assertEqual(package["missingRequiredHeroes"], [])
        names = {row["name"] for row in package["rows"]}
        self.assertIn("UPLB Oblation", names)
        self.assertIn("UPLB Freedom Park", names)
        self.assertIn("Charles Fuller Baker Memorial Hall", names)
        self.assertTrue(any("Umali" in name for name in names))
        self.assertIn("Molawin Creek", names)

    def test_priority_modify_preserves_provider_evidence_and_appends_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            review_path = Path(directory) / "review.json"
            shutil.copyfile(ROOT / "data" / "reviews" / "vertical-slice-review.json", review_path)
            before = json.loads(review_path.read_text(encoding="utf-8"))["rows"][0]
            modify_priority(before["candidateId"], review_path=review_path, name="Corrected name", aliases=["Alias"], canonical_id="uplb:test:one", verification={"identity": "provisional"}, selected_geometry_source="osm", notes="fixture correction", reviewed_at="2026-08-17")
            after = next(row for row in json.loads(review_path.read_text(encoding="utf-8"))["rows"] if row["candidateId"] == before["candidateId"])
            self.assertEqual(after["name"], "Corrected name")
            self.assertEqual(after["externalIds"], before["externalIds"])
            self.assertEqual(after["sourceGeometry"], before["sourceGeometry"])
            self.assertEqual(after["provenance"], before["provenance"])
            self.assertEqual(after["reviewHistory"][-1]["action"], "modify")

    def test_review_corrections_survive_accept_and_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            review_path = Path(directory) / "review.json"
            markdown_path = Path(directory) / "review.md"
            shutil.copyfile(ROOT / "data" / "reviews" / "vertical-slice-review.json", review_path)
            before = json.loads(review_path.read_text(encoding="utf-8"))["rows"][0]
            candidate_id = before["candidateId"]
            modify_priority(
                candidate_id,
                review_path=review_path,
                name="Owner corrected landmark",
                aliases=["Owner alias"],
                verification={"identity": "human-reviewed", "position": "human-reviewed"},
                selected_geometry_source="osm",
                notes="Owner review provenance",
                reviewed_at="2026-08-17T10:00:00+08:00",
            )
            decide_priority(
                candidate_id,
                "accept",
                review_path=review_path,
                reviewed_at="2026-08-17T10:05:00+08:00",
                review_method="project-owner",
                evidence_refs=["data/reviews/vertical-slice-review.json"],
                reason="Accepted for POC greybox",
            )
            build_priority_package(
                output_path=review_path,
                markdown_path=markdown_path,
                generated_at="2026-08-17",
            )
            after = next(row for row in json.loads(review_path.read_text(encoding="utf-8"))["rows"] if row["candidateId"] == candidate_id)
            self.assertEqual(after["name"], "Owner corrected landmark")
            self.assertEqual(after["aliases"], ["Owner alias"])
            self.assertEqual(after["verification"], {"identity": "human-reviewed", "position": "human-reviewed"})
            self.assertEqual(after["currentDecision"], "accept")
            self.assertEqual(after["review"]["reviewMethod"], "project-owner")
            self.assertTrue(after["reviewHistory"])
            self.assertEqual(after["sourceGeometry"], before["sourceGeometry"])
            self.assertEqual(after["provenance"], before["provenance"])

    def test_approved_review_snapshot_is_explicit_and_complete(self) -> None:
        snapshot = json.loads((ROOT / "data" / "reviews" / "approved" / "vertical-slice-review-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["reviewVersion"], "v1")
        self.assertEqual(snapshot["approvalStatus"], "approved")
        self.assertEqual(snapshot["reviewer"], "project-owner")
        self.assertTrue(snapshot["approvedAt"])
        self.assertTrue(snapshot["sourcePackageHash"].startswith("sha256:"))
        self.assertTrue(snapshot["sourceCandidateHash"].startswith("sha256:"))
        self.assertEqual(len(snapshot["rows"]), 25)
        self.assertTrue(all(row["currentDecision"] == "accept" for row in snapshot["rows"]))
        baker = next(row for row in snapshot["rows"] if row["registryMatch"] == "uplb:building:baker-hall")
        self.assertEqual(baker["verification"]["identity"], "human-reviewed")
        self.assertEqual(baker["verification"]["position"], "human-reviewed")
        self.assertEqual(baker["verification"]["facade"], "unknown")
        self.assertEqual(baker["verification"]["interior"], "unknown")
        self.assertIn("sourceGeometry", baker)
        self.assertIn("provenance", baker)

    def test_future_priority_prefers_central_unnamed_connector(self) -> None:
        hero = ProviderCandidate(
            id="candidate:hero",
            provider="osm",
            feature_type="landmark",
            name="UPLB Oblation",
            geometry={"type": "Point", "coordinates": [121.24155, 14.165]},
            provenance=("source:osm:test",),
            external_ids={"osm": "node/hero"},
            confidence={},
        )
        central = ProviderCandidate(
            id="candidate:central",
            provider="osm",
            feature_type="walkway",
            name="OSM walkway central",
            geometry={"type": "LineString", "coordinates": [[121.2414, 14.1649], [121.2417, 14.1651]]},
            provenance=("source:osm:test",),
            external_ids={"osm": "way/central"},
            confidence={},
        )
        distant_named = ProviderCandidate(
            id="candidate:distant",
            provider="osm",
            feature_type="walkway",
            name="Recreation Path",
            geometry={"type": "LineString", "coordinates": [[121.247, 14.17], [121.2475, 14.1702]]},
            provenance=("source:osm:test",),
            external_ids={"osm": "way/distant"},
            confidence={"surface": "high"},
        )
        connectivity = {central.id: 3, distant_named.id: 0}
        central_score = priority_score(central, "walkway/pedestrian", None, [hero], connectivity, {central.id})
        distant_score = priority_score(distant_named, "walkway/pedestrian", None, [hero], connectivity, set())
        self.assertGreater(central_score, distant_score)

    def test_srtm_datum_metadata_is_unambiguous(self) -> None:
        source = next(item for item in json.loads((ROOT / "data" / "canonical" / "source-records.json").read_text(encoding="utf-8"))["sources"] if item["id"] == "source:dem:srtm-baseline")
        metadata = source["metadata"]
        self.assertEqual(metadata["horizontalCRS"], "EPSG:4326")
        self.assertEqual(metadata["horizontalDatum"], "WGS84")
        self.assertEqual(metadata["verticalDatum"], "EGM96")
        self.assertEqual(metadata["verticalUnits"], "metres")
        self.assertNotIn("WGS84 ellipsoid referenced to EGM96 geoid", json.dumps(source))

    def test_overture_update_check_is_read_only_and_pinned(self) -> None:
        result = check_updates(ROOT / "config" / "overture.json", fetch=False)
        self.assertEqual(result["pinnedRelease"], "2026-06-17.0")
        self.assertEqual(result["currentOfficialPublishedRelease"], "2026-06-17.0")
        self.assertFalse(result["updateAvailable"])

    def test_review_schema_is_part_of_artifact_validation(self) -> None:
        self.assertEqual(validate_artifacts(ROOT), [])


if __name__ == "__main__":
    unittest.main()
