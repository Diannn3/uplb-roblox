from __future__ import annotations

import json

from tools.geodata.transform import CoordinateTransform
from tools.modeling.placement import build_placement_binding
from tools.modeling.registry import ROOT


def _inputs():
    snapshot = json.loads((ROOT / "data/modeling/reference/baker-canonical-snapshot.geojson").read_text(encoding="utf-8"))
    spec = json.loads((ROOT / "data/modeling/building-specs/baker-hall.v0.3.json").read_text(encoding="utf-8"))
    manifest = {"assetId": spec["artifactContract"]["assetId"]}
    return snapshot, spec, manifest


def test_baker_placement_binding_round_trips_model_local_to_scene_local() -> None:
    snapshot, spec, manifest = _inputs()
    feature = snapshot.get("feature") or snapshot
    transform = CoordinateTransform()
    lon, lat = feature["geometry"]["coordinates"][0][0][:2]
    east, north, _ = transform.wgs84_to_local(lon, lat)
    scene = {
        "featureId": spec["proposedFeatureId"],
        "placement": {"eastM": east, "northM": north, "relativeElevationM": 4.25},
    }
    binding = build_placement_binding(
        feature_snapshot=snapshot,
        production_spec=spec,
        asset_manifest=manifest,
        scene_object=scene,
    )
    assert binding["softwareTransformValidation"]["status"] == "pass"
    assert binding["softwareTransformValidation"]["maxPlanarErrorM"] <= 1e-5
    assert binding["sceneTransform"]["translationLocalMeters"][2] == 4.25
    assert binding["sourceUncertaintySeparated"] is True
    assert binding["bindingHash"].startswith("sha256:")
