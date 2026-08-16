# Vertical-slice greybox visual review gate

This is the required hard stop before any Roblox Studio or MCP handoff.

## Engineering state

- Phase 1 revision: `validation:phase1-closure-v1`
- Approved review: `v1`, project-owner snapshot
- Selected features: `95` (`5` heroes plus deterministic candidate context)
- Canonical features: `3`; context candidates retain `sourceLifecycle: candidate`
- Semantic world manifest: `data/generated/greybox-v0.1/world-manifest.json`
- Structural QA: `pass`; duplicate IDs, missing source IDs, non-finite values, negative dimensions, and absurd local extents were checked
- Determinism: semantic manifest comparison `pass`

## Terrain state

- SRTMGL1.003 and NASADEM_HGT.001 are both documented and acquisition-ready through current Earthdata routes.
- No Earthdata raster or credentials were available for this run.
- `config/terrain.json` therefore keeps `baseline: null`.
- `data/generated/terrain-comparison/` and `data/generated/terrain-v0.1/` are synthetic fixture artifacts only; they do not select or validate a NASA baseline.

## Blender state

The official Blender 5.x headless contract is documented in
[`docs/TERRAIN_AND_GREYBOX_POC.md`](TERRAIN_AND_GREYBOX_POC.md). No Blender
executable was found on PATH, so the checked-in output is a semantic Python
fallback with `conditional-blender-unavailable` status. It is not a `.blend`
mesh validation.

Fixed-camera preview paths:

- `data/generated/greybox-v0.1/previews/topdown.png`
- `data/generated/greybox-v0.1/previews/oblation.png`
- `data/generated/greybox-v0.1/previews/freedom-park.png`
- `data/generated/greybox-v0.1/previews/baker-context.png`
- `data/generated/greybox-v0.1/previews/dl-umali-context.png`
- `data/generated/greybox-v0.1/previews/road-level.png`

## Human stop

Visual approval is **pending**. Do not proceed to Roblox Studio/MCP until the
project owner has reviewed the terrain comparison, world manifest, structural
QA, and all six previews. AI inspection can record uncertainties, but cannot
replace the owner’s visual approval.

Known uncertainties: no real DEM baseline, no Blender mesh, no facade/interior
detail, no survey-grade geometry, and no campus-wide visual verification.

## Automated/semantic preview findings

The fallback previews show a bounded central cluster with required hero markers
and candidate context; local coordinates stay within the expected slice extent.
Because these are marker previews rather than Blender terrain/meshes, inverted
terrain, floating/buried buildings, road alignment, and player-scale plausibility
remain unverified. Those checks belong to the owner-approved Blender/Studio pass.
