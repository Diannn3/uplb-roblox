from __future__ import annotations

import sys
import unittest

from tools.worldgen.preflight import build_preflight


class PreflightTests(unittest.TestCase):
    def test_preflight_reports_capabilities_without_secret_values(self) -> None:
        report = build_preflight(
            blender_probe=lambda: {"available": False, "version": None, "executable": None, "diagnostic": "not found"},
            earthdata_probe=lambda: {"libraryAvailable": False, "authenticated": False, "diagnostic": "install earthaccess and configure Earthdata Login"},
            roblox_probe=lambda: {"configured": False, "diagnostic": "Roblox Studio MCP is not exposed"},
        )

        self.assertEqual(report["python"]["required"], "3.12+")
        self.assertEqual(report["python"]["version"], ".".join(map(str, sys.version_info[:3])))
        self.assertEqual(report["blender"]["available"], False)
        self.assertEqual(report["earthdata"]["authenticated"], False)
        self.assertEqual(report["robloxMcp"]["configured"], False)
        serialized = str(report)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("token", serialized.lower())


if __name__ == "__main__":
    unittest.main()
