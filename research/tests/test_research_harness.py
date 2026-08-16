from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import importlib.util
import json
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "research" / "scripts" / "validate_research.py"
REQUIREMENTS = ROOT / "research" / "requirements.txt"
COMPARE = ROOT / "research" / "scripts" / "osm_overture_compare.py"


class ResearchHarnessTests(unittest.TestCase):
    def test_validator_runs_against_utf8_markdown(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("PASS: research package validation succeeded", result.stdout)

    def test_coordinate_dependency_is_declared(self) -> None:
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertRegex(requirements, r"(?m)^pyproj(?:[<>=!~].*)?$")

    def test_osm_overture_reader_handles_utf8_json(self) -> None:
        spec = importlib.util.spec_from_file_location("osm_overture_compare", COMPARE)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "utf8.json"
            path.write_text(json.dumps({"name": "Oblation ñ"}), encoding="utf-8")
            self.assertEqual(module.read_json(path)["name"], "Oblation ñ")

    def test_fetch_failure_is_recorded_without_aborting_comparison(self) -> None:
        spec = importlib.util.spec_from_file_location("osm_overture_compare", COMPARE)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        notes: list[str] = []

        def failed_fetch(output: Path) -> None:
            output.write_bytes(b"")
            raise OSError("HTTP Error 504: Gateway Timeout")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "osm.json"
            ok = module.fetch_with_note("OSM", failed_fetch, output, notes)
            self.assertFalse(output.exists())

        self.assertFalse(ok)
        self.assertEqual(len(notes), 1)
        self.assertIn("OSM fetch failed", notes[0])
        self.assertIn("504", notes[0])

    def test_overture_cli_failure_is_converted_to_actionable_error(self) -> None:
        spec = importlib.util.spec_from_file_location("osm_overture_compare", COMPARE)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        completed = subprocess.CompletedProcess(
            args=["overturemaps"],
            returncode=1,
            stdout="",
            stderr="Exception: Could not fetch STAC catalog: HTTP Error 404: Not Found\n",
        )
        with patch.object(module.subprocess, "run", return_value=completed):
            with self.assertRaises(RuntimeError) as context:
                module.fetch_overture(Path("overture.geojson"))

        self.assertIn("STAC catalog", str(context.exception))
        self.assertIn("404", str(context.exception))


if __name__ == "__main__":
    unittest.main()
