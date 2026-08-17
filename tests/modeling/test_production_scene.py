from __future__ import annotations

from copy import deepcopy

from tools.modeling.production_scene import bind_production_assets


def test_binding_adds_asset_without_mutating_canonical_geometry_or_placement() -> None:
    scene = {
        "metadata": {},
        "objects": [
            {
                "id": "scene:uplb:building:baker-hall",
                "featureId": "uplb:building:baker-hall",
                "geometry": {"type": "Polygon", "coordinatesLocalMeters": [[[0, 0], [1, 0], [1, 1]]]},
                "placement": {"eastM": 10, "northM": 20, "relativeElevationM": 3},
            }
        ],
    }
    before = deepcopy(scene)
    binding = {
        "featureId": "uplb:building:baker-hall",
        "sourceFeatureId": "uplb:building:baker-hall",
        "assetId": "uplb-baker-hall-v0.3",
        "modelSpace": {"units": "meters"},
        "sceneTransform": {"translationLocalMeters": [1, 2, 3]},
        "robloxTransformContract": {"metersPerStud": 0.28},
        "bindingHash": "sha256:" + "a" * 64,
    }
    result = bind_production_assets(scene, [binding])
    assert scene == before
    assert result["objects"][0]["geometry"] == before["objects"][0]["geometry"]
    assert result["objects"][0]["placement"] == before["objects"][0]["placement"]
    assert result["objects"][0]["productionAsset"]["assetId"] == "uplb-baker-hall-v0.3"
    assert result["metadata"]["productionAssetBinding"]["status"] == "pass"
