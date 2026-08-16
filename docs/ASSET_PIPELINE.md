# 3D Asset and Reconstruction Pipeline

## 1. Principle

A real UPLB feature is not a mesh. It is a canonical feature with evidence; one or more meshes/parts/materials are representations that can be regenerated or replaced.

Production sequence:

```text
canonical feature + reference bundle
  -> building/asset specification
  -> greybox in real dimensions
  -> choose production method
  -> model/generate
  -> optimize + UV/material
  -> collision proxy
  -> LOD/streaming grouping
  -> Roblox import
  -> bind asset manifest to canonical feature ID
  -> visual/spatial/performance QA
```

## 2. Asset classes

### A — Parametric infrastructure

Examples: roads, sidewalks, curbs, simple fences, simple stairs, drainage edges, generic walls.

Method: generated from spatial specs with Blender Python/Geometry Nodes or deterministic Studio tooling.

Goal: regenerate after GIS edits; no one-off manual placement where geometry can be derived.

### B — Reusable campus kit

Examples: lamp posts, benches, bins, bollards, planters, sign frames, generic doors/windows, railings, awnings.

Method: model once in Blender or use vetted Creator Store source, then instantiate. AI generation can create candidates, but final kit assets are normalized to project scale/material/triangle/collision rules.

### C — Modular architectural kit

Examples: repeated window bays, brise-soleil/sunshades, columns, covered-walk modules, roof edges, gutters, stair/railing families.

Method: human/AI-assisted Blender modeling from verified dimensions/ratios. This is the highest-leverage way to reproduce multiple UPLB buildings consistently.

### D — Unique building/landmark

Examples: Baker Hall, DL Umali, Oblation context, Main Library, distinctive facades.

Method: footprint + measured/estimated massing + modular facade + selective custom meshes. AI may create subcomponents, but the building silhouette and proportions are manually verified.

### E — Photogrammetry/reference-derived landmark

Examples: sculptures, monuments, unusual small structures, texture/material references.

Method: owned/authorized image set → Meshroom/COLMAP → dense/high-detail reference → retopologized low-poly production mesh. Never ship raw reconstruction by default.

## 3. Building specification contract

Each building gets a `building-spec.json` containing:

- stable feature ID;
- footprint source and confidence;
- local/world placement;
- estimated/verified dimensions;
- floor count/height evidence;
- facade sides and reference IDs;
- architectural family/kit;
- required modules;
- material palette;
- interior tier;
- triangle/texture/collision budgets;
- LOD plan;
- unresolved questions;
- human acceptance checklist.

## 4. Reference-image-to-building workflow

For a candidate such as Baker Hall:

1. Resolve canonical footprint and orientation.
2. Gather only permitted/owned references; index by facade direction/date.
3. Establish at least one trustworthy scale cue (known door size is not automatically trustworthy; prefer measured/official dimensions).
4. Build a plain massing model at correct footprint/height.
5. Segment the facade into repeated bays/modules.
6. Model one verified representative module.
7. Instantiate modules procedurally where repetition is regular.
8. Create custom deviations only where the real building differs.
9. Use low-resolution shared material sets/trim sheets before unique textures.
10. Import to Studio, place through canonical transform, compare screenshots/reference viewpoints.
11. Record discrepancies and confidence.

The pipeline should prefer a correct, modular 80% facade over an AI-generated opaque mesh that looks plausible but cannot be corrected systematically.

## 5. Blender automation

Recommended scripts:

- import canonical GeoJSON and transform to local metres;
- create building footprint curves;
- extrude simple massing by height/levels;
- sweep road/path profiles;
- project infrastructure to terrain;
- instance building-kit modules;
- enforce naming/scale/origin conventions;
- generate collision proxy collections;
- export selected models to FBX/GLTF with manifest metadata.

BlenderGIS can assist with georeferencing and GIS imports, but project automation should not depend on opaque interactive state. [BlenderGIS](https://github.com/domlysz/BlenderGIS), accessed 2026-08-17.

## 6. Roblox AI generation

Roblox Assistant currently supports generated materials, meshes and procedural models, and documents bounding-box-constrained mesh generation and triangle limits. [Assistant](https://create.roblox.com/docs/assistant/guide), accessed 2026-08-17.

Studio MCP currently exposes `generate_mesh`, `generate_material`, and `generate_procedural_model`. [MCP](https://create.roblox.com/docs/studio/mcp), accessed 2026-08-17.

### Approved initial uses

- generic prop candidate;
- visual blockout;
- low-stakes background clutter;
- reusable primitive procedural models;
- material prototype.

### Human review required

- every generated mesh's geometry/silhouette;
- triangle count;
- UV/texture behavior;
- scale;
- collision;
- visual match to reference;
- licensing/provenance of the reference input.

### Do not assume

- MCP exposes every Assistant UI capability;
- image-conditioned generation through MCP unless current MCP docs/tool schema confirms it;
- generated architecture is factually accurate;
- generated textures reproduce institutional marks correctly or permissibly.

## 7. Creator Store strategy

Creator Store is useful for generic assets only when provenance and quality are clear.

Import gate:

1. record asset ID/creator/source/license/terms;
2. import into quarantine collection;
3. inspect all scripts and nested objects;
4. remove unnecessary scripts/remotes/constraints;
5. inspect triangle/material/texture/collision cost;
6. normalize scale/pivots/naming;
7. compare art direction;
8. approve into asset manifest.

Do not assemble the campus from visually inconsistent free models.

## 8. Photogrammetry

Meshroom and AliceVision are MPL-2.0; COLMAP is a BSD-licensed SfM/MVS alternative. [Meshroom](https://github.com/alicevision/Meshroom), [COLMAP](https://colmap.github.io/license.html), accessed 2026-08-17.

Recommended use is **reference capture**, especially for small complex landmarks.

Pipeline:

```text
owned/authorized overlapping photos
  -> lens/image QA
  -> SfM cameras / sparse cloud
  -> dense reconstruction
  -> cleanup / scale calibration
  -> high-res reference mesh
  -> manual/automated retopology
  -> UV / texture bake
  -> low-poly production mesh
  -> collision proxy + LOD
  -> Roblox import
```

Do not use Google Street View as the input photo set.

## 9. Internal asset budgets

Roblox's hard general mesh limit is 20,000 triangles per mesh. [Roblox mesh specs](https://create.roblox.com/docs/art/modeling/specifications), accessed 2026-08-17.

Project budgets below are **initial targets, not platform limits**:

| Asset class | Geometry target | Texture target | Collision |
|---|---:|---:|---|
| tiny prop | 100–800 tris | shared/128–256 | box/hull/no collision |
| normal prop | 500–2,500 | 256–512 | simplified proxy |
| landmark prop | 2,000–8,000 | 512–1024 | custom simple proxy |
| repeated facade module | 300–2,000 | trim/shared 256–512 | normally simple/no per-detail collision |
| normal building exterior module set | 5k–20k total visible modules near player | shared trim + selective 512 | primitive hulls/walls |
| hero exterior | modular, each mesh comfortably <20k | mostly 512; selective 1024 | explicit proxy model |

Roblox's texture documentation supports 4K uploads but explicitly recommends much smaller images based on object size to reduce memory. [Texture specs](https://create.roblox.com/docs/art/modeling/texture-specifications), accessed 2026-08-17.

## 10. LOD strategy

- Split buildings by semantic/render groups, not arbitrary tiny fragments.
- Use `MeshPart.RenderFidelity = Automatic` or `Performance` where visually acceptable.
- Use model-level LOD/SLIM only after testing current behavior and visual quality.
- Replace detailed window geometry with normal/albedo/trim treatment at distance.
- Avoid transparent foliage overdraw explosions; use compact canopy cards/meshes and distance variants.
- Disable shadows on small/distant props that do not materially affect scene identity.

Roblox specifically recommends streaming and render-fidelity/LOD controls as performance levers. [Performance guidance](https://create.roblox.com/docs/performance-optimization/improve), accessed 2026-08-17.

## 11. Collision strategy

Visual geometry is not collision geometry.

- terrain handles natural ground;
- simple boxes/wedges define building walls/steps where possible;
- complex meshes use Box/Hull or dedicated proxy MeshParts;
- vegetation usually has trunk-only or no collision;
- decorative railings should not force complex per-triangle collision;
- accessibility routes receive dedicated collision/walkability QA.

## 12. Architectural families

During data collection, tag each building with a provisional architectural family. Then identify cross-building modules:

- modern concrete classroom block;
- historic/heritage structure;
- laboratory/research block;
- covered-walk system;
- dormitory/residential;
- utilitarian/service structure.

The exact taxonomy should emerge from a 15–20-building visual audit, not be invented solely from names.

## 13. First asset-pipeline proof

Use the first vertical slice to produce exactly:

- one deterministic road/path segment;
- one generic bench/lamp asset;
- one AI-generated low-stakes prop candidate;
- one modular facade kit;
- one hero landmark exterior;
- one vegetation kit;
- one collision/LOD validation report.

If these cannot be reproduced cleanly from specs, do not scale production to the full campus.
