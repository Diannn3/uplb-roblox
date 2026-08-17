from __future__ import annotations

import unittest

from tools.blender.gates import build_execution_gates


class ExecutionGateTests(unittest.TestCase):
    def test_fixture_and_unavailable_blender_are_not_reported_as_real_passes(self) -> None:
        gates = build_execution_gates(
            semantic_status="pass",
            terrain_source_kind="synthetic-fixture",
            blender_available=False,
            mesh_status="not-run",
            render_status="not-run",
            visual_status="pending-human",
            roblox_status="not-run",
        )

        self.assertEqual(gates["semanticGate"], "pass")
        self.assertEqual(gates["terrainRealDataGate"], "blocked")
        self.assertEqual(gates["blenderAvailableGate"], "blocked")
        self.assertEqual(gates["blenderMeshGate"], "not-run")
        self.assertEqual(gates["blenderRenderGate"], "not-run")
        self.assertEqual(gates["blenderVisualGate"], "pending-human")
        self.assertEqual(gates["robloxGenerationGate"], "not-run")


if __name__ == "__main__":
    unittest.main()
