# UPLB Roblox — Campus Modeling Implementation Plan

## Current starting point

This implementation targets the validated vertical-slice architecture already
present on `feat/approved-roblox-validation-v0-1`: real NASADEM terrain,
deterministic scene spec, Blender rendering, and disposable Roblox validation.
The content-production system must preserve those contracts rather than replace
them.

## 12 production phases

### Phase 1 — Source recovery and model registry — **IMPLEMENTED FOUNDATION**

Implemented here:
- source evidence registry,
- building production registry,
- source-recovery queue,
- strategy classifier,
- Baker Hall production specification.

Next: add the rest of the campus from reviewed candidate/canonical data and begin
institutional/source outreach outside automated tooling.

### Phase 2 — Campus-wide geospatial expansion — **EXISTING PIPELINE, NOT EXPANDED HERE**

Extend the proven canonical/scene-spec pipeline from the current controlled slice
to developed UPLB in geographic waves. Do not auto-promote the full OSM AOI.

### Phase 3 — UPLB Architecture Kit — **V0.1 IMPLEMENTED**

Machine-readable families, modules, material classes, dimensions, and default
Roblox budgets are now defined. Primitive OBJ prototypes are generated to prove
the handoff.

### Phase 4 — Procedural building generator — **MASSING CORE IMPLEMENTED**

The new modeling package can project WGS84 footprints to EPSG:32651-local meter
geometry, deterministically extrude valid footprints to OBJ, and compile an
unverified facade-bay placement plan for standard buildings. Baker Hall is the
first massing prototype; its facade remains intentionally ungenerated until
reference measurements are available.

### Phase 5 — Central hero slice — **NEXT VISUAL PRODUCTION MILESTONE**

Order:
1. Baker Hall.
2. Oblation (permission/recovery first).
3. Physical Sciences (permission/recovery first).
4. Main Library.
5. DL Umali.
6. Student Union/CAS/Carillon context.

Replace greyboxes in-place; do not change canonical placement to fit art.

### Phase 6 — Roads / campus infrastructure

Promote reusable curb, drainage, covered walkway, sign, lamp, bench, fence, and
utility modules. Keep roads/path centerlines and terrain binding data-driven.

### Phase 7 — Vegetation / environment

Build species/style pools with deterministic seeded placement by vegetation zone;
manually place only landmark vegetation. Prefer reused meshes/materials to unique
trees per instance.

### Phase 8 — Campus production waves

Suggested waves:
- central/CAS,
- CEAT,
- agriculture/forestry/vet,
- biology/research,
- dorms/housing,
- recreation,
- administration/support,
- peripheral developed campus.

Each wave follows `research -> greybox -> source-ready -> modeling -> QA -> Roblox`.

### Phase 9 — Asset optimization and import/reimport

Every production building gets master + LODs + collision + material/texture
manifest. Keep stable mesh names so Roblox Reimport can update existing
MeshParts/models without rebuilding Roblox-specific configuration.

### Phase 10 — Streaming and performance

Keep instance streaming enabled. Use reusable meshes, modest texture resolution,
`SLIM` LOD on suitable static groups, and measured performance budgets. Split
spatially huge models into sensible modules rather than forcing one enormous
atomic building/world object.

### Phase 11 — Reality validation

For every important feature compare:
- canonical placement,
- Blender/master dimensions,
- Roblox transform,
- reference photographs/measurements,
- walking scale and sight lines.

Never conflate software transform precision with source-data uncertainty.

### Phase 12 — polish / living campus

Only after physical-world quality and performance are stable: lighting, ambient
sound, signage polish, selective interiors, navigation, NPCs, interaction, and
gameplay.

## Definition of scalable completion

“All of UPLB” does not mean every object is bespoke. A realistic target is:

- 10–25 custom hero assets,
- 8–15 verified architectural families,
- 50–100 reusable campus modules,
- procedural accurate/context buildings,
- zone-based vegetation and infrastructure,
- detailed interiors only where product/gameplay requires them.
