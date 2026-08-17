from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tools.modeling.evidence import EvidenceError, production_orientation_gate, validate_reference_profile_v02
from tools.modeling.registry import ROOT


def _profile() -> dict:
    return json.loads((ROOT / "data/modeling/reference/baker-hall.reference-profile.v0.2.json").read_text(encoding="utf-8"))


def test_baker_v02_reference_profile_has_referential_integrity() -> None:
    report = validate_reference_profile_v02(_profile())
    assert report["status"] == "pass"
    assert report["sourceCount"] >= 8
    assert report["observationCount"] >= 6


def test_missing_observation_source_is_rejected() -> None:
    profile = deepcopy(_profile())
    profile["observations"][0]["evidenceIds"] = ["source:missing"]
    report = validate_reference_profile_v02(profile)
    assert report["status"] == "fail"
    assert any("missing evidence source" in row for row in report["errors"])


def test_capability_mismatch_is_rejected() -> None:
    profile = deepcopy(_profile())
    profile["observations"][0]["capability"] = "interior"
    report = validate_reference_profile_v02(profile)
    assert report["status"] == "fail"
    assert any("not declared capable" in row for row in report["errors"])


def test_proxy_orientation_is_allowed_only_at_prototype_stage() -> None:
    spec = {
        "productionTier": "hero-exterior",
        "productionStage": "prototype",
        "orientation": {"policy": "longest-edge-proxy", "reviewStatus": "unreviewed", "evidenceIds": []},
    }
    assert production_orientation_gate(spec)["status"] == "pass"
    spec["productionStage"] = "visual-review"
    gate = production_orientation_gate(spec)
    assert gate["status"] == "fail"
    assert gate["reasons"]


def test_reviewed_hero_orientation_can_pass_visual_review_gate() -> None:
    spec = {
        "productionTier": "hero-exterior",
        "productionStage": "visual-review",
        "orientation": {
            "policy": "reviewed-source-edge",
            "reviewStatus": "reviewed",
            "evidenceIds": ["source:image:example"],
        },
    }
    assert production_orientation_gate(spec)["status"] == "pass"
