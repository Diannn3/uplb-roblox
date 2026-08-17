# UPLB Architecture Kit v0.1

## Goal

Model the entire developed campus by reusing a small number of accurately
researched architectural modules and building families rather than manually
creating hundreds of unrelated meshes.

The authoritative machine-readable kit is:

`data/modeling/architecture-kit-v0.1.json`

## Initial families

- `uplb-historic-prewar` — bespoke historic assets such as Baker Hall.
- `uplb-concrete-academic-midcentury` — repeated reinforced-concrete academic bays.
- `uplb-concrete-academic-late20c` — later academic/admin grid systems.
- `uplb-concrete-service-1970s` — health/service/support structures.
- `uplb-modern-glass-concrete` — contemporary glass/concrete structures.

Families are hypotheses until a representative sample of real UPLB buildings is
measured/reviewed. They do not establish architectural truth by themselves.

## Initial reusable components

The kit includes stable IDs for:

- jalousie and aluminum/glass windows,
- double and service doors,
- square/round concrete columns,
- horizontal and vertical sunshades,
- flat/gable/hip/low-slope roof families,
- steel railings,
- stairs and ramps,
- covered walkways,
- curbs and open drainage,
- benches, lamps, bollards, fences, wayfinding signs, and utility boxes.

The generated OBJ files under `assets/uplb-kit/prototypes/` validate dimensions
only. Replace them with visually researched modules while keeping the IDs stable.

## Procedural building contract

A standard campus building should eventually compile from:

```text
canonical footprint
+ verified/projected base elevation
+ storeys / height
+ architecture family
+ facade bay observations
+ selected kit modules
+ material classes
= deterministic building master
```

Hero assets may bypass procedural facade generation while still using shared
materials, collision rules, provenance, and asset manifests.

## Roblox asset policy

Current Roblox guidance favors individually reusable assets instead of importing
an entire map as one unique mesh set. Repeated mesh IDs should be reused so the
engine can instance them. Instance streaming should remain enabled for a large
world, and static building groups are candidates for `Model.LevelOfDetail = SLIM`.

Production exports should therefore be stable per building/module, for example:

```text
BLDG_Baker_LOD0.glb
BLDG_Baker_LOD1.glb
KIT_Window_Jalousie_A.glb
KIT_Curb_A.glb
```

Do not export `UPLB_entire_campus.glb` as the core production workflow.

## Texture strategy

- reuse material classes and trim sheets;
- reserve 1024 px maps for important hero surfaces that actually need them;
- use 512/256 px or native Roblox materials for most repeating campus modules;
- avoid unique near-identical textures for repeated windows/curbs/props;
- keep glass/transparency layering conservative to reduce overdraw.
