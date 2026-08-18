"""Baker Wave 03: reviewed frontage + visual-review production asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .baker_hall_v04 import OUTPUT_DIR, compile_baker_v04, generate_baker_v04
from .freshness import regenerate_and_compare
from .registry import ROOT
from .wave03_binding import build as build_binding, write as write_binding

REPORT_PATH = ROOT / "data/modeling/modeling-wave03-report.json"


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def build_report(freshness: dict[str, Any] | None = None) -> dict[str, Any]:
    _, baker = compile_baker_v04()
    binding = build_binding()
    report = {
        "schemaVersion": "uplb-modeling-wave03-report-v0.1",
        "waveId": "baker-wave03-reviewed-frontage-v0.1",
        "status": "pass",
        "baker": {
            "productionStage": baker["productionStage"],
            "orientation": baker["orientation"],
            "orientationGate": baker["orientationGate"],
            "frontageContext": baker["frontageContext"],
            "visualReviewGate": "pending-human",
            "placementBindingStatus": binding["softwareTransformValidation"]["status"],
        },
        "freshness": freshness,
        "hardStops": [
            "Baker v0.4 is a visual-review asset, not survey-grade architecture.",
            "Project-owner visual approval is still required before production-ready promotion.",
            "Side/rear opening layouts and exact roof ridge/eave geometry remain evidence gaps.",
            "Roblox GLB/FBX import, Reimport, spatial QA, and playtest remain pending.",
        ],
        "nextGate": "Run real Blender Baker v0.4 build and campus preview, then project-owner visual review.",
    }
    if baker["status"] != "pass":
        report["status"] = "fail"
    if binding["softwareTransformValidation"]["status"] != "pass":
        report["status"] = "fail"
    if freshness and freshness["status"] != "pass":
        report["status"] = "fail"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--check-freshness", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    compile_baker_v04()
    if args.generate:
        generate_baker_v04()
        write_binding()

    freshness = regenerate_and_compare(OUTPUT_DIR, lambda out: generate_baker_v04(out)) if args.check_freshness else None
    report = build_report(freshness=freshness)

    if args.write_report:
        _write(REPORT_PATH, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
