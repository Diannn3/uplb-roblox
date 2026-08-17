"""Generate the offline Roblox terrain voxel budget report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.geodata.io import read_json, write_json

from .terrain_budget import estimate_terrain_budget


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=ROOT / "data/generated/worldgen-v0.1/scene-spec.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/generated/roblox-v0.1/terrain-performance.json")
    args = parser.parse_args()
    report = estimate_terrain_budget(read_json(args.scene))
    write_json(args.output, report)
    print(json.dumps({"afterProcessedCells": report["afterProcessedCells"], "beforeLogicalCells": report["beforeLogicalCells"], "reductionRatio": report["reductionRatio"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

