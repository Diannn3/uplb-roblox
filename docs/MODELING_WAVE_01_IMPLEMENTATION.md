# UPLB Modeling Production Wave 01

**Implementation date:** 2026-08-17
**Base:** `feat/campus-content-production-foundation` / `27754a4`
**Scope:** finish Baker Hall v0.2, then prove the evidence-aware production pipeline on the first central-campus building wave.

## What this wave actually models

| Building | Source identity | Production identity | Output level |
| --- | --- | --- | --- |
| Baker Hall | canonical `uplb:building:baker-hall` | canonical | reference-derived hero exterior v0.2 |
| DL Umali Hall | `candidate:osm:way/33541381` | proposed `uplb:building:dl-umali-hall` | tall auditorium proxy + facade frame |
| Student Union | `candidate:osm:way/37450035` | proposed `uplb:building:student-union` | 3-level concrete/glass proxy |
| Physical Sciences | `candidate:osm:way/44076412` | proposed `uplb:building:physical-sciences` | 3-level concrete academic proxy |
| ULKC / Main Library candidate | `candidate:osm:way/1098780830` | proposed `uplb:building:university-library-knowledge-center` | **massing only** |
| CAS Annex 2 | `candidate:osm:way/486667196` | proposed `uplb:building:cas-annex-2` | 2-level academic proxy |
| Dean Edelwina C. Legaspi Hall | `candidate:osm:way/33541786` | proposed `uplb:building:dean-edelwina-legaspi-hall` | 2.5-level academic proxy |

The proposed `uplb:*` IDs above are production handles. They do not mutate the canonical geodata registry.

## Baker Hall v0.2

Baker is intentionally finished first because it is the first hero-building proof of the content pipeline.
The generator preserves the canonical footprint and adds only reference-supported broad morphology:

- two-storey body;
- central projecting balcony/portico;
- four prominent upper round columns;
- simplified lower supports;
- balustrade rhythm;
- floor/cornice bands;
- flanking facade bays and green-awning proxy modules;
- central sign/parapet mass;
- shallow, explicitly provisional central gable.

Exact dimensions, side/rear facade details, basement, interior, and roof geometry remain replaceable.
The selected facade edge is the longest footprint edge solely for deterministic generation; it is not a surveyed orientation claim.

## Evidence discipline

The source registry now includes or retains:

- the 2014 UPLB virtual-campus paper/model-recovery lead;
- Baker Commons photographs and UPLB archive/conservation leads;
- a CC BY-SA 4.0 Student Union photograph;
- a CC BY-SA 4.0 DL Umali photograph;
- a CC BY-SA 4.0 IBS photograph;
- a CC BY-SA 4.0 Bienvenido M. Gonzales Hall photograph, kept separate from the unresolved/current ULKC candidate state;
- UPLB Commons and ArcGIS/StoryMap discovery indexes;
- OSM-derived metadata leads for IBS and CEM pending acquisition through the project's own geodata pipeline.

No reference-photo binaries are committed here.

## Geometry implementation

The common compiler is `tools/modeling/reference_building.py`.

It performs:

1. JSON-schema validation of the production spec and reference profile.
2. Exact source-feature ID check against the pinned feature snapshot.
3. WGS84 → UTM Zone 51N footprint projection.
4. Footprint-preserving extrusion.
5. Optional level bands from source-supported level counts.
6. Optional removable facade proxies from evidence-aware presets.
7. Explicit deferral of unsupported roof geometry.
8. QA and triangle-budget checks.
9. Deterministic OBJ/report/QA generation with source/proposed identity metadata.

### Important geometry fix

`tools/modeling/mesh.py` now uses Shapely's **constrained Delaunay triangulation** for polygon caps.
The previous unconstrained Delaunay approach could bridge concave boundaries and leave complex footprints such as
Physical Sciences non-watertight. All seven production OBJs in this wave were independently checked with `trimesh`
and are watertight after the fix.

## Source gaps intentionally not papered over

`data/modeling/next-wave-source-gaps.json` blocks geometry generation where evidence is insufficient:

- **Oblation:** reusable scan permission/source still unresolved.
- **IBS:** OSM way lead + licensed photo known, actual polygon must be pinned through project geodata first.
- **CEM:** OSM way lead exists, but individual building vs college-complex identity must be resolved.
- **CEAT:** must be decomposed into present-day buildings/wings rather than pretending "CEAT" is one building.
- **CAS Annex 1 / CDC:** legacy model leads exist, but current footprint snapshots still need to be frozen.
- **UPLB Gate:** should use a landmark/measurement workflow rather than normal building extrusion.

## Commands

```powershell
python -m pytest -q
python -m tools.modeling.pipeline --check --generate-prototypes --generate-baker-production --generate-central-wave --write-report
python -m compileall -q tools tests
```

## Next production gates

1. Visually review Baker before treating its proportions as the historic-UPLB facade standard.
2. Recover or request the 2014 model archive in parallel.
3. Pin IBS/CEM/CEAT/CAS Annex 1/CDC footprints through the geodata lifecycle.
4. Build a dedicated Oblation/sculpture pipeline after reuse permission or an authorized fresh reconstruction source exists.
5. Replace the central-wave proxy facades incrementally as better elevations/measurements are acquired.
