from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.geodata.overture_check_updates import check_updates
from tools.geodata.phase_gate import build_gate
from tools.geodata.review import modify_priority
from tools.geodata.review_priority import build_priority_package
from tools.geodata.schemas import validate_artifacts


ROOT = Path(__file__).resolve().parents[2]


class PhaseOneClosureTests(unittest.TestCase):
    def test_closure_exposes_explicit_gates_and_stops_before_worldgen(self) -> None:
        report = build_gate()
        payload = report.to_dict()
        self.assertEqual(report.engineering_gate, "pass")
        self.assertEqual(report.canonical_identity_gate, "pass")
        self.assertEqual(report.geometry_gate, "pass")
        self.assertEqual(report.reproducibility_gate, "pass")
        self.assertEqual(report.human_review_gate, "pending")
        self.assertEqual(report.dem_rights_gate, "pass")
        self.assertEqual(report.overture_comparison_gate, "blocked")
        self.assertFalse(report.worldgen_ready)
        self.assertFalse(report.campus_wide_production_ready)
        self.assertFalse(payload["worldgenReady"])

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

    def test_overture_update_check_is_read_only_and_pinned(self) -> None:
        result = check_updates(ROOT / "config" / "overture.json", fetch=False)
        self.assertEqual(result["pinnedRelease"], "2026-06-17.0")
        self.assertEqual(result["currentOfficialPublishedRelease"], "2026-06-17.0")
        self.assertFalse(result["updateAvailable"])

    def test_review_schema_is_part_of_artifact_validation(self) -> None:
        self.assertEqual(validate_artifacts(ROOT), [])


if __name__ == "__main__":
    unittest.main()
