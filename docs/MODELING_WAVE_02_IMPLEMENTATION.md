# UPLB Modeling Wave 02 — Evidence Integration and Production Binding

**Source branch:** `feat/modeling-wave01-continuation`  
**Source commit:** `43cb34ad567ebbdecccee258413351fa00658dda`  
**Wave:** `modeling-wave02-evidence-integration-v0.1`

## Purpose

Wave 01 proved that UPLB footprints can be turned into deterministic, evidence-aware OBJ prototypes. Wave 02 makes that system safe to scale into production assets. It does **not** declare Baker Hall architecturally complete, and it does not promote candidate geodata or make Blender/Roblox authoritative.

The central contract is now:

```text
reviewed/canonical geodata
        ↓
scene specification (placement + terrain authority)
        ↓
production asset specification (art/evidence authority)
        ↓
placement binding
        ↓
Blender asset build / Roblox import
```

Art may replace a greybox but may not move canonical geometry to make a model fit.

## Implemented

### 1. Evidence contract v0.2

`tools/modeling/evidence.py` and the v0.2 schemas introduce typed evidence capabilities and controlled confidence/rights vocabularies. Observations can distinguish evidence that supports identity, footprint, height, levels, facade, orientation, roof, materials, historical state, geometry, landscaping, or interiors.

A hero asset may remain a prototype with proxy orientation, but it cannot silently advance to visual-review/production status with `longest-edge-proxy` or an unknown orientation.

### 2. Facade orientation is now an explicit reviewable decision

`tools/modeling/orientation.py` supports:

- `unknown`
- `longest-edge-proxy`
- `reviewed-source-edge`
- `reviewed-azimuth`
- `entrance-anchor`
- `legacy-model-derived`
- `field-measured`

Reviewed policies require reviewed evidence. Wave 02 deliberately leaves Baker at `longest-edge-proxy` and `productionStage=prototype`; this prevents accidental architectural approval of an orientation inferred only for deterministic generation.

### 3. Production placement binding

`tools/modeling/placement.py` formalizes the translation from centroid-local model metres back into the project coordinate system and then Roblox studs. The binding records:

- source/production identities,
- model origin in EPSG:32651,
- scene-local translation,
- Roblox axis/scale transform,
- software transform validation,
- a deterministic binding hash.

The existing `scene-spec.json` remains authoritative for placement and terrain. A compact `production-asset-bindings.json` registry points from scene identity to production asset and binding without committing a second multi-megabyte copy of the scene.

### 4. Polygon holes and MultiPolygon geometry

`tools/modeling/geometry_v2.py` adds production-oriented projection/extrusion for Polygon and MultiPolygon features, including inner rings/courtyards. Constrained triangulation is used for caps and all boundary rings receive side walls.

### 5. Formal topology QA

`tools/modeling/topology.py` and the updated `qa.py` gate each prospective Roblox MeshPart independently for:

- valid face indices,
- non-degenerate faces,
- finite vertices,
- edge incidence,
- boundary/open edges,
- over-connected/non-manifold edges,
- isolated vertices,
- connected-component reporting,
- watertightness,
- per-part triangle limits,
- aggregate building budget,
- maximum MeshPart count.

Overlapping modular parts are allowed at the assembly level; each importable MeshPart itself must remain valid.

### 6. Roblox budgets now distinguish building aggregate from MeshPart limits

The current Roblox production contract caps an individual imported mesh at 20,000 triangles. Wave 02 therefore separates:

- aggregate LOD budget,
- per-MeshPart triangle budget,
- maximum MeshPart count,
- material-slot budget,
- collision policy.

A hero building may be more than 20k triangles in aggregate only if it is deliberately split into individually valid MeshParts.

### 7. Baker Hall v0.3 production prototype

Wave 02 generates a new Baker artifact set without deleting v0.2. It has stable reimport-oriented names:

```text
Baker__Shell_A
Baker__Portico
Baker__FrontWindows
Baker__FrontAwnings
Baker__Bands
Baker__Parapet
Baker__Roof
Baker__Collision
```

It emits:

- LOD0 / LOD1 / LOD2 / LOD3 combined deterministic debug OBJ files,
- individual OBJ files for every actual MeshPart,
- collision proxy,
- v0.2 production asset manifest,
- production report.

The front orientation and several proportions remain reference-derived/provisional. This is intentional.

### 8. Blender production-asset consumer

`tools/blender/build_production_asset.py` runs **inside Blender** and consumes the Baker asset manifest. It:

- recreates each stable MeshPart from deterministic OBJ geometry,
- preserves project meter/X-east/Y-north/Z-up semantics internally,
- stamps provenance custom properties,
- rechecks the per-mesh triangle ceiling,
- saves a `.blend`,
- exports each LOD to GLB and FBX for a later Roblox import bakeoff,
- exports collision geometry,
- writes a Blender QA report.

Blender is not available in the ChatGPT execution container, so no Blender render/export approval is claimed by this wave bundle itself.

### 9. Clean-regeneration/freshness gate

`tools/modeling/freshness.py` and `tools/modeling/wave02.py` can regenerate Baker v0.3 into a temporary directory and compare generated OBJ/JSON artifacts. Placement binding and compact binding registry are regenerated from the repository's authoritative scene and compared as well.

CI now calls:

```powershell
python -m tools.modeling.wave02 --check --check-freshness
```

and watches `assets/generated/production/**`.

## Baker approval gates

Wave 02 intentionally stops Baker at these states:

```text
geometry/topology gate       PASS after deterministic generation
placement binding gate       generated from authoritative scene locally
Blender structural gate      PENDING LOCAL BLENDER
Blender visual gate          PENDING HUMAN
Roblox GLB/FBX bakeoff        PENDING DISPOSABLE STUDIO
Roblox spatial gate          PENDING BAKER VISUAL APPROVAL + IMPORT
architectural approval       PENDING STRONGER ORIENTATION/MEASUREMENT EVIDENCE
```

Do not change these to `pass` merely because an OBJ exists.

## Next execution after this wave is ingested

1. Run the Wave 02 local application script so the exact scene-backed Baker placement binding is generated.
2. Run all tests and clean-regeneration checks.
3. Run Blender locally using the manifest.
4. Review real Baker renders against the evidence pack.
5. Resolve Baker facade orientation with reviewed evidence before architectural approval.
6. After owner visual approval, test GLB vs FBX in a disposable Roblox Studio place.
7. Freeze stable import hierarchy and reimport behavior.
8. Only then apply the same end-to-end process to DL Umali, Student Union, Physical Sciences, CAS Annex 2, and Dean Legaspi Hall.

## Explicit non-goals

- no whole-campus detailed generation in this wave,
- no candidate-to-canonical identity promotion,
- no interiors,
- no unlicensed scan ingestion,
- no automatic AI hero mesh as authoritative geometry,
- no production-place Roblox edits,
- no claim that Baker v0.3 is survey-accurate,
- no migration of the legacy `main-library-ulck` output paths yet; the typo is recorded in `identifier-migrations.json` for an atomic later migration.
