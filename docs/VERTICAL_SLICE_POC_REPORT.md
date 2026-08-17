# UPLB Roblox — Vertical Slice Realization Report

Date: 2026-08-17  
Branch: `feat/terrain-blender-roblox-poc`  
Implementation commits: `55e9064`, `913fff1`, `0962fbe`, `0636eee`

## Current decision

The first deterministic vertical slice is implemented and locally validated on
the disposable Roblox Studio place. It is a greybox realization only. The
runtime is deliberately marked `blocked-fixture-terrain` until a licensed real
DEM is downloaded, processed, and compared. No fixture output is being claimed
as production campus elevation.

## Evidence and source gates

| Gate | Result | Evidence |
| --- | --- | --- |
| OSM source pin | Pass | Existing canonical source registry and pinned retrieval hash |
| Overture recovery | Blocked, explicit | Existing provider diagnostic; adapter remains available |
| Earthdata CMR search | Pass | [`earthdata_search_smoke.json`](../research/results/earthdata_search_smoke.json), anonymous metadata-only search for SRTMGL1.003 and NASADEM_HGT.001 |
| Earthdata download | Blocked | Local `earthaccess` 0.18.0 is installed, but no local Earthdata Login credentials are present |
| DEM license/provenance | Pending download record | SRTM/NASADEM provider metadata is known; archive and payload hashes are not yet recorded |
| First-slice traceability | Pass for fixture | 98 scene features preserve feature IDs, candidate IDs, source geometry hashes, verification state, and scene/terrain revisions |

The only required external action is local Earthdata authentication through the
official Earthdata Login flow. Credentials must stay in the local credential
store (`_netrc`/`netrc` or the approved earthaccess interactive flow); they are
not requested in chat and are not committed.

## Deterministic foundation

- `tools/terrain/` now supports strict 1-arc-second HGT dimensions, NumPy
  decoding, ceil-based AOI coverage, relative/absolute elevation provenance,
  and SRTM/NASADEM comparison metadata.
- `tools/worldgen/compile_scene.py` emits terrain-following 3D route ribbons,
  building foundation samples, vertical-reference metadata, and conservative
  scene validation.
- `tools/roblox/generate_scene_luau.py` emits an ASCII-only compact Luau
  runtime projection with stable ordering and a source SHA-256 header.
- `src/Shared/CoordinateTransform.lua` is the shared local-metre/Roblox-stud
  contract (`0.28 m/stud`, east `+X`, north `-Z`, elevation `+Y`).
- `src/Server/WorldGenerator.lua` owns Terrain `WriteVoxels` at 4-stud
  resolution, 64-cell chunks, terrain-following route segments, owned
  regeneration, and provenance attributes.

## Blender fixture gate

Blender 5.0.0 was discovered at the local installation path and consumed the
same scene specification. The headless build produced:

- `vertical-slice-v0.1.blend`
- `blender-qa.json` and `determinism.json`
- six deterministic renders (`topdown`, `oblation`, `freedom-park`, `baker`,
  `dl-umali`, `road-level`)
- 107 semantic objects with `semanticSceneEqual: true`

The renders are greybox review material. Human visual approval remains open;
the fixture terrain is intentionally not a production visual claim.

## Roblox MCP disposable-place gate

Roblox Studio MCP was verified against the unsaved `Place1` Edit/Play data
model. The server and client source boundaries were mirrored into the place.
The generated root is `Workspace.GeneratedVerticalSlice_v01` with the required
`Buildings`, `Roads`, `Walkways`, `Water`, `GreenSpaceDebug`, `Landmarks`,
`Debug`, and `Metadata` folders.

Observed Play-mode result:

- 43 footprint objects
- 574 terrain-following route segments
- 272 smooth-Terrain chunks (`1071 × 17 × 983` cells)
- 5 landmark/hero parts, including Oblation, Freedom Park, Baker Hall, DL
  Umali, and the Main Library
- nonzero terrain occupancy observed at the Oblation spawn
- server and client initialization logs present
- short character-navigation probe passed
- a second regeneration produced the same scene hash and counts
- the long cross-slice navigation probe remains blocked pending navmesh/pathing
  tuning against real terrain

Machine-readable details are in
[`poc-validation.json`](../data/generated/roblox-v0.1/poc-validation.json).

## Tests

The Python 3.12 environment reports `70 passed`. This includes HGT/CRS
golden-point tests, deterministic ingestion and scene tests, Earthdata adapter
fallback tests, Blender tests, Luau generator tests, and server-contract tests.

## Next gate

Authenticate Earthdata locally, then run the two approved granule downloads,
record archive/payload checksums, generate strict real SRTM/NASADEM terrain,
select the baseline with the comparison report, regenerate the scene/Luau,
rerun Blender, and repeat the disposable-place Roblox validation. Until that
cycle is complete, keep the fixture status and human visual gate explicit.

