from __future__ import annotations

import json
from pathlib import Path

from tools.modeling import wave02


def test_wave02_generates_binding_registry_and_freshness_with_scene(monkeypatch, tmp_path) -> None:
    baker_dir = tmp_path / "baker"
    binding_path = tmp_path / "bindings" / "baker.json"
    registry_path = tmp_path / "production-asset-bindings.json"
    report_path = tmp_path / "wave02-report.json"
    scene_path = tmp_path / "scene-spec.json"

    scene_path.write_text(
        json.dumps(
            {
                "metadata": {},
                "objects": [
                    {
                        "id": "scene:uplb:building:baker-hall",
                        "featureId": "uplb:building:baker-hall",
                        "candidateId": "candidate:osm:way/37449973",
                        "placement": {
                            "eastM": 100.0,
                            "northM": -200.0,
                            "baseElevationM": 6.0,
                            "relativeElevationM": 6.0,
                        },
                        "geometry": {"type": "Polygon", "coordinatesLocalMeters": [[[0, 0], [1, 0], [1, 1]]]},
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(wave02, "BAKER_OUTPUT_DIR", baker_dir)
    monkeypatch.setattr(wave02, "BAKER_BINDING_PATH", binding_path)
    monkeypatch.setattr(wave02, "BINDING_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(wave02, "REPORT_PATH", report_path)
    monkeypatch.setattr(wave02, "SCENE_SPEC_PATH", scene_path)

    result = wave02.generate_outputs(require_scene=True)
    assert result["binding"]["softwareTransformValidation"]["status"] == "pass"
    assert binding_path.exists()
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["records"][0]["scenePlacementAuthority"] == "canonical-scene"

    freshness = wave02.check_freshness(require_scene=True)
    assert freshness["status"] == "pass"
    assert freshness["bakerArtifacts"]["status"] == "pass"
    assert freshness["placementBinding"]["status"] == "pass"
