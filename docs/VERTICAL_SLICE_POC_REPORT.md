# UPLB Roblox — Real-Terrain Vertical Slice Report

Date: 2026-08-17  
Branch: `feat/approved-roblox-validation-v0-1`

## Decision

The outdoor Oblation/Freedom Park/Baker Hall slice now has a deterministic,
source-traceable real-terrain foundation and an approved disposable Roblox
handoff. Overture is still explicitly blocked; OSM remains the canonical
feature source. Math Building interiors and gameplay mechanics remain deferred.
This is greybox validation, not final architecture. The authoritative state is
[`data/generated/worldgen-v0.1/poc-gates.json`](../data/generated/worldgen-v0.1/poc-gates.json),
now `ROBLOX_VERTICAL_SLICE_VALIDATED`.

## Evidence gate

| Gate | Result | Evidence |
| --- | --- | --- |
| OSM pin | Pass | `data/canonical/` and the pinned candidate hash |
| Overture | Blocked, explicit | `research/results/overture_fallback_probe.json`; no coverage claim |
| Earthdata acquisition | Pass | SRTMGL1.003 and NASADEM_HGT.001 granules downloaded through the official Earthdata route; credentials remain local |
| DEM comparison | Pass | `data/generated/terrain-comparison/comparison.json`; 0 nodata samples in both products |
| Selected baseline | NASADEM_HGT.001 | Equal-coverage tuple is lower across nodata, max adjacent delta, p95 adjacent delta, and spikes; NASADEM `10.427534 m / 5.243241 m / 151` vs SRTM `11.056161 m / 5.760314 m / 217`, both nodata `0` |
| Rights/provenance | Pass | DOI, retrieval time, granule, archive/payload/processed hashes in `terrain-manifest.json` and `config/terrain.json` |

Selected terrain artifacts:

- product: `NASADEM_HGT.001`, granule `NASADEM_HGT_n14e121`
- archive: `sha256:c115ac7027d4c6160b308ac280b5e259309680ed6347475407cb071194a42398`
- HGT payload: `sha256:730d5350ef7663eb7ae00f9cbe861549156540a055dc75d6efaa4f0d19a7fbe9`
- processed heightfield: `sha256:3e6dcd85e480cbfaaea342bc18a8d48290af4adff0e7af55bcb72e7144438e84`
- local CRS: EPSG:32651; horizontal datum WGS84; vertical datum EGM96; world base 22 m

## Canonical scene

`data/generated/worldgen-v0.1/scene-spec.json` is `ready`, validates with no
errors or warnings, and contains `98` objects: 5 heroes, 35 context buildings,
25 roads, 25 walkways, 5 waterways, and 3 green-space features. Waterways now
use terrain-following centerlines/ribbons rather than placeholder cubes.

The scene preserves the terrain granule and all archive/payload/processed hashes.
The generated server module is
`src/Server/Generated/WorldScene.lua`; the heavy module is intentionally not in
`ReplicatedStorage`.

## Blender gate

Blender 5.0.0 consumed the same scene spec. Structural mesh and render QA pass
with `semanticSceneEqual: true`, 108 semantic objects, all required
collections, no duplicate IDs, no non-finite transforms, no degenerate faces,
and seven deterministic cameras.
Review copies are available in [`docs/assets/vertical-slice-real-terrain/`](assets/vertical-slice-real-terrain/):

- [topdown.png](assets/vertical-slice-real-terrain/topdown.png)
- [oblation.png](assets/vertical-slice-real-terrain/oblation.png)
- [freedom-park.png](assets/vertical-slice-real-terrain/freedom-park.png)
- [baker-context.png](assets/vertical-slice-real-terrain/baker-context.png)
- [dl-umali-context.png](assets/vertical-slice-real-terrain/dl-umali-context.png)
- [road-level.png](assets/vertical-slice-real-terrain/road-level.png)
- [library-context.png](assets/vertical-slice-real-terrain/library-context.png)

Human visual approval is recorded in
[`data/reviews/approved/blender-vertical-slice-review-v1.json`](../data/reviews/approved/blender-vertical-slice-review-v1.json).
It covers the seven real-terrain renders and the greybox handoff only; no
detailed interior or final asset claim is made.

## Roblox approved validation

The connected disposable auto-recovery place was synced from Git. The authoritative
module is under `ServerScriptService.Server.Generated.WorldScene`; the stale
`ReplicatedStorage.Shared.Generated.WorldScene` was removed. Edit-mode bake and
final standard-module regeneration both passed with:

- scene hash: `sha256:809b58f648934c19cba70878b37b8956866331994679148a07e95e7410806ea6`
- 43 footprint objects, 709 route segments, 480 terrain chunks
- historical voxel cells: `1890 × 124 × 983` (`230375880` total)
- terrain bounds: `-5420,2140,-8,488,-572,3360`
- 35 buildings, 5 landmarks/heroes, 300 water segments, and an Oblation-derived
  spawn offset 12 m east of the hero proxy
- root status: `ready`; terrain revision: `terrain-v0.2-real`

Production-static Play mode logged “using existing baked world” and did not
regenerate the terrain. The server and client placed the character at the
generated spawn, and a short navigation to `(80, 72, 0)` completed within four
studs. Long-distance navigation remains deferred. Machine-readable details are in
[`poc-validation.json`](../data/generated/roblox-v0.1/poc-validation.json).

The offline generator audit reports `230,375,880` baseline logical cells versus
`25,274,544` processed cells (`89.0289973%` reduction) across `480` bounded
chunks in [`terrain-performance.json`](../data/generated/roblox-v0.1/terrain-performance.json).

## Tests and remaining review

The Python 3.12 suite reports `100 passed` on this branch. This includes strict HGT dimensions,
CRS/axis golden points, real-product comparison metrics, deterministic scene and
Luau generation, Blender geometry compatibility, Overture diagnostics, and
server/runtime contracts.

Remaining review items are a future long-distance navigation/pathfinding pass
and the still-blocked Overture provider. No raw
DEM archives, credentials, Roblox publication, or external permission requests
are committed or sent.
