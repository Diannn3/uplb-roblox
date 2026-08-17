$ErrorActionPreference = "Stop"
$dest = Join-Path $PSScriptRoot "..\vendor-research"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Set-Location $dest

if (-not (Test-Path "basic-procedural-building")) { git clone --depth 1 "https://github.com/achrefelouafi/BasicProceduralBuilding.git" "basic-procedural-building" }
if (-not (Test-Path "modular-tree")) { git clone --depth 1 "https://github.com/GoodPie/modular_tree.git" "modular-tree" }
# REVIEW LICENSE FIRST: git clone "https://github.com/vvoovv/bcga.git" "bcga"
# REVIEW LICENSE FIRST: git clone "https://github.com/Durman/BuildingNodes.git" "buildingnodes"
if (-not (Test-Path "blosm")) { git clone --depth 1 "https://github.com/vvoovv/blosm.git" "blosm" }
if (-not (Test-Path "lune")) { git clone --depth 1 "https://github.com/lune-org/lune.git" "lune" }
if (-not (Test-Path "luau-roblox")) { git clone --depth 1 "https://github.com/Scythe-Technology/luau-roblox.git" "luau-roblox" }
if (-not (Test-Path "bloxforge")) { git clone --depth 1 "https://github.com/princeofscale/bloxforge.git" "bloxforge" }

Write-Host "Done. Review LICENSE_MATRIX.csv before copying anything into your project."
