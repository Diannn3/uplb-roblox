#!/usr/bin/env bash
set -euo pipefail
DEST="$(cd "$(dirname "$0")/.." && pwd)/vendor-research"
mkdir -p "$DEST"
cd "$DEST"

if [ ! -d "basic-procedural-building" ]; then git clone --depth 1 "https://github.com/achrefelouafi/BasicProceduralBuilding.git" "basic-procedural-building"; fi
if [ ! -d "modular-tree" ]; then git clone --depth 1 "https://github.com/GoodPie/modular_tree.git" "modular-tree"; fi
# REVIEW LICENSE FIRST: git clone "https://github.com/vvoovv/bcga.git" "bcga"
# REVIEW LICENSE FIRST: git clone "https://github.com/Durman/BuildingNodes.git" "buildingnodes"
if [ ! -d "blosm" ]; then git clone --depth 1 "https://github.com/vvoovv/blosm.git" "blosm"; fi
if [ ! -d "lune" ]; then git clone --depth 1 "https://github.com/lune-org/lune.git" "lune"; fi
if [ ! -d "luau-roblox" ]; then git clone --depth 1 "https://github.com/Scythe-Technology/luau-roblox.git" "luau-roblox"; fi
if [ ! -d "bloxforge" ]; then git clone --depth 1 "https://github.com/princeofscale/bloxforge.git" "bloxforge"; fi

echo "Done. Review LICENSE_MATRIX.csv before copying anything into your project."
