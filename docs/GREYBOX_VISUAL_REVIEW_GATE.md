# Vertical-slice greybox visual review gate

This is the required hard stop before any approved Roblox Studio or MCP handoff.
The single authoritative machine-readable state is
[`data/generated/worldgen-v0.1/poc-gates.json`](../data/generated/worldgen-v0.1/poc-gates.json).

## Engineering state

- Phase 1 revision: `validation:real-terrain-v0.2`
- Approved review: engineering gate complete; project-owner visual sign-off remains pending
- Selected features: `98` (`5` heroes, `35` context buildings, `25` roads, `25` walkways, `5` waterways, and `3` green-space features)
- Canonical scene: `data/generated/worldgen-v0.1/scene-spec.json`
- Structural QA: `pass`; duplicate IDs, missing source IDs, non-finite values, negative dimensions, and absurd local extents were checked
- Determinism: semantic manifest comparison `pass`
- Shared scene spec: `data/generated/worldgen-v0.1/scene-spec.json` (`ready`, NASADEM_HGT.001 selected)
- Roblox validation: `data/generated/roblox-v0.1/poc-validation.json`
- Historical fixture gates: `data/generated/greybox-v0.1/` (all marked `superseded`; do not use them as current POC state)

## Terrain state

- SRTMGL1.003 and NASADEM_HGT.001 were acquired through Earthdata and recorded with archive and payload hashes.
- NASADEM_HGT.001 is the selected baseline because its equal-coverage evidence tuple is lower across max adjacent discontinuity, p95 adjacent discontinuity, and spike count (`10.427534 m`, `5.243241 m`, `151`) than SRTM (`11.056161 m`, `5.760314 m`, `217`); both products have zero nodata samples.
- `config/terrain.json` is `ready-real-terrain` and records the selected granule, retrieval time, processed heightfield hash, and terrain revision.
- `data/generated/terrain-comparison/` retains the deterministic side-by-side comparison; `data/generated/terrain-v0.1/` is the selected processed terrain artifact.

## Blender state

The official Blender 5.x headless contract is documented in
[`docs/TERRAIN_AND_GREYBOX_POC.md`](TERRAIN_AND_GREYBOX_POC.md). Blender 5.0
completed the headless build and structural/render QA (`pass`, `108` objects, `7`
renders, deterministic scene equality). Review copies are published under
`docs/assets/vertical-slice-real-terrain/`; the generated `.blend` remains
ignored.

Fixed-camera preview paths:

- `assets/vertical-slice-real-terrain/topdown.png`
- `assets/vertical-slice-real-terrain/oblation.png`
- `assets/vertical-slice-real-terrain/freedom-park.png`
- `assets/vertical-slice-real-terrain/baker-context.png`
- `assets/vertical-slice-real-terrain/dl-umali-context.png`
- `assets/vertical-slice-real-terrain/road-level.png`
- `assets/vertical-slice-real-terrain/library-context.png`

## Human stop

Visual approval is **pending-human**. A prior disposable Roblox Studio run is
retained and classified as `robloxEngineeringDryRun: pass`; the project owner must still review the
terrain comparison, scene manifest, Blender QA, and all seven renders before
any approved Roblox rerun, publication, or detailed gameplay work. AI inspection can record uncertainties,
but cannot replace the owner’s visual approval.

Known uncertainties: no facade/interior detail, no survey-grade geometry, no
campus-wide visual verification, and Overture remains explicitly blocked.

## Automated/semantic preview findings

The rendered slice shows the bounded central cluster on the selected NASADEM
terrain with required hero markers and context. Blender and Studio checks cover
terrain-following placement, route ribbons, oriented proxies, spawn provenance,
and deterministic regeneration. The offline Roblox terrain budget estimates
`230,375,880` baseline logical cells versus `25,274,544` processed cells
(`89.0289973%` reduction) across 480 bounded chunks. Facade/interior detail,
navmesh behavior, and player-scale judgment remain part of the owner-approved
follow-up pass.
