# Execution Roadmap

## Phase 0 — Evidence closure and permissions

**Goal:** close the research gaps that require network execution or data-owner responses.

**Inputs:** this research package, source register.  
**Tasks:** run live OSM/Overture comparison; inventory official UPLB GIS/map resources; request LiPAD/UPLB/IMS permissions; verify Mapillary/KartaView UPLB coverage; confirm chosen DEM endpoint/license.  
**Ownership:** CODEX-AUTOMATABLE + REQUIRES PERMISSION/DATA REQUEST.  
**Acceptance:** pinned raw extract hashes and comparison report exist; source status is explicit; no restricted data in Git.  
**Blockers:** institutional response time.  
**Fallback:** proceed with OSM/Overture + legal 30 m DEM and mark confidence.

### Current execution status (2026-08-17)

- OSM AOI retrieval is complete and hash-pinned in `research/results/osm_overture_comparison.json`.
- The official Overture client returned a STAC 404; the bounded direct-cloud probe timed out. Both outcomes are recorded as blocked provider access, not as missing coverage.
- Permission requests are drafted locally in `docs/PERMISSION_REQUEST_TEMPLATES.md` and have not been sent.
- Phase 1 contracts, CRS transforms, OSM normalization, Overture parsing adapter, provenance records, conflation review records, validation, canonical GeoJSON, and generated Luau are implemented on the feature branch.
- SRTMGL1.003 and NASADEM_HGT.001 are acquired and hash-recorded; NASADEM_HGT.001 is the selected 30 m baseline after deterministic comparison.
- The evidence gate is accepted for the controlled outdoor OSM-first vertical slice. Overture remains explicitly blocked with no coverage claim; campus-wide production remains gated on institutional sources and human review.
- The hardening branch now separates raw/candidate/canonical/generated data, persists `data/canonical/identity-registry.json`, uses Shapely validity/intersection checks, and emits an offline CI/Phase 1 hardening report.
- The canonical vertical-slice source set remains traceable to the approved Oblation/Freedom Park/Baker Hall cluster; the generated real-terrain scene expands it to deterministic context routes, buildings, waterways, and green space for greybox validation.
- The real-terrain Blender/Roblox handoff is complete on the disposable validation place; human visual approval, navmesh/performance review, and detailed interiors remain deferred.

## Phase 1 — Canonical geospatial foundation

**Goal:** implement data schemas, CRS library, source ingest and canonical-feature registry.

**Outputs:** `data/raw` policy, normalized candidate format, canonical GeoJSON, provenance registry, schema validator, generated local coordinates.  
**Ownership:** CODEX-AUTOMATABLE.  
**Acceptance:** representative buildings/paths round-trip; every canonical property traces to source; no hand-edited generated output.

## Phase 2 — Greybox world generator

**Goal:** produce an automatically regenerable low-detail campus slice.

**Outputs:** terrain preview, road/path geometry, building extrusions, feature labels/markers.  
**Ownership:** CODEX-AUTOMATABLE + CODEX + BLENDER + CODEX + ROBLOX MCP.  
**Acceptance:** a changed footprint regenerates and repositions the Roblox blockout without manual cleanup; spatial validation passes.

## Phase 3 — Terrain and hardscape calibration

**Goal:** make slopes, roads, creek/retaining structures and building pads believable.

**Inputs:** chosen DEM, verified paths, local evidence.  
**Ownership:** CODEX + BLENDER + HUMAN VISUAL QA; HUMAN DATA COLLECTION for problem areas.  
**Acceptance:** vertical slice traverses without obvious grade/terrain artifacts; main landmarks sit at plausible relative elevations.

## Phase 4 — Asset kit pipeline

**Goal:** establish art direction and reusable campus modules before hero-building production.

**Outputs:** material palette, trim sheets, vegetation kit, props, windows/doors/railings/covered-walk modules, asset manifest workflow.  
**Ownership:** CODEX + BLENDER, CODEX + ROBLOX MCP, HUMAN VISUAL QA.  
**Acceptance:** kits meet budgets and visually cohere across at least two buildings.

## Phase 5 — Vertical slice

**Recommended area:** the Oblation / Freedom Park / Baker Hall cluster, expanded only as necessary to include one normal academic building and a road/path loop. The stored vertical-slice AOI is a research starting envelope, not a final legal boundary.

**Why:** recognizable UPLB identity, mixed hardscape/green space, strong test of terrain, landmark geometry, roads, vegetation, and streaming.

**Must include:**

1. real CRS placement;
2. legal DEM-derived terrain + local refinement;
3. at least one road and pedestrian route;
4. procedural/reusable vegetation;
5. one standard building greybox/exterior;
6. one hero landmark/building (Baker Hall is candidate);
7. one low-stakes AI-generated prop that passes review;
8. one vetted reusable/library prop;
9. StreamingEnabled;
10. automated spatial/asset validation;
11. screenshot/reference visual QA;
12. representative mobile profiling.

**Acceptance:** the complete source→world→QA pipeline works without hidden manual source-of-truth steps.

## Phase 6 — First detailed interior pilot

**Candidate:** Math Building, because IMS already has stable room/floor/routing semantics.

Before use, site/authorized plans must calibrate its deliberately non-geographic poster-derived geometry.

**Goal:** prove building-local coordinates, floor transforms, door/stair bindings, selective interior streaming and semantics.  
**Acceptance:** one floor/route is metrically calibrated and verified; no emergency-route claims are invented.

## Phase 7 — Campus sector expansion

Expand sector-by-sector rather than building-by-building randomly. Each sector must reach a completeness gate before the next becomes P0.

Suggested production order after the vertical slice is validated:

1. central/lower-campus academic-social core;
2. adjacent CAS/library/student-service cluster;
3. CEAT/research sectors;
4. housing/support sectors;
5. upper campus/Forestry and stronger terrain/vegetation zones;
6. peripheral research/technology areas as evidence and performance permit.

Final order must be based on verified feature inventory and gameplay value, not this provisional list alone.

## Phase 8 — Navigation and experience layer

Bind feature IDs to orientation/tour/navigation interactions without altering canonical geometry. Reuse Room TBA/IMS concepts where license and semantics fit.

Potential features: searchable campus map, landmark discovery, freshman orientation, tours, building information, social spaces, event hooks.

## Phase 9 — Gameplay systems

Only after reconstruction pipeline is stable. Possible layers include quests, campus life, transport/jeepney systems and events. Server-authoritative systems remain separate from map generation.

## Phase 10 — Optimization, accessibility and release

Run broad mobile profiling, streaming audits, collision/accessibility QA, attribution/legal review, content moderation checks, onboarding, and staged releases.

# First 20 implementation tasks

Each task is intentionally atomic enough for an agent to complete and review.

1. **[CODEX-AUTOMATABLE] Run the live OSM/Overture AOI comparison** using `research/scripts/osm_overture_compare.py --fetch`; commit only result hashes/summary, not replaceable raw bulk data. *(OSM is complete; Overture is currently blocked and explicitly deferred.)*
2. **[CODEX-AUTOMATABLE] Extend the comparison with IoU/centroid/area matching** and a manually reviewable landmark sample report.
3. **[REQUIRES PERMISSION/DATA REQUEST] Open data requests** for current UPLB campus GIS/boundary/building metadata, LiPAD Los Baños coverage, and authorized IMS dimensional/floor-plan references.
4. **[CODEX-AUTOMATABLE] Create production JSON Schemas** from the research contracts for source records, canonical features and building specs, with fixtures/tests.
5. **[CODEX-AUTOMATABLE] Implement `tools/geodata/transform.py`** using EPSG:4326→32651→local metres with explicit project scale config and golden tests.
6. **[CODEX-AUTOMATABLE] Implement OSM ingest** for buildings, roads, paths, waterways, entrances and selected landuse within the AOI; persist immutable raw manifest/hash separately from normalized data.
7. **[CODEX-AUTOMATABLE] Implement Overture building ingest** for the pinned release and AOI; preserve `sources`, GERS-style ID, height/floor attributes and license attribution.
8. **[CODEX-AUTOMATABLE] Implement candidate normalization/conflation** that never silently merges conflicts and emits review records.
9. **[HUMAN VISUAL QA] Review the first 25 canonical feature identities** against current permitted/official references and mark confidence/property conflicts.
10. **[CODEX-AUTOMATABLE] Create canonical vertical-slice GeoJSON** for the approved landmark cluster with stable IDs and provenance.
11. **[CODEX-AUTOMATABLE] Acquire and preprocess the approved baseline DEM** with CRS/vertical-datum metadata; generate a local heightfield preview, not Roblox production terrain yet. *(Complete for the controlled NASADEM-backed slice.)*
12. **[CODEX + BLENDER] Build a deterministic Blender greybox script** that imports canonical features, sets metric scale, creates building massing and road/path preview geometry.
13. **[CODEX-AUTOMATABLE] Define generated-world manifest format** linking each generated object to feature ID, generator version and source hash.
14. **[CODEX + ROBLOX MCP] Create a disposable Studio greybox collection** from the vertical-slice manifest and verify transform/scale against known feature markers. *(Complete for the real-terrain slice; no place was published.)*
15. **[CODEX-AUTOMATABLE] Implement first Studio/world validation checks** for missing feature IDs, unanchored static objects, source-hash drift and out-of-tolerance placement.
16. **[HUMAN DATA COLLECTION] Capture/curate an authorized reference set** for one hero landmark/building and one normal building, with per-image rights records.
17. **[CODEX + BLENDER] Create the first reusable architectural kit** (one window bay, door, column/rail/covered-walk module as evidence supports), with triangle/material/collision budgets.
18. **[CODEX + ROBLOX MCP] Generate one low-stakes AI prop candidate** inside a bounding box, record generation parameters, then run geometry/collision/visual review before promotion.
19. **[HUMAN VISUAL QA] Complete vertical-slice screenshot and device QA**; log discrepancies, streaming behavior, frame-time/memory results and art-direction issues.
20. **[CODEX-AUTOMATABLE] Freeze Vertical Slice v1 evidence**: source hashes, canonical-data revision, asset manifests, Studio source snapshot decision, validation report, and a go/no-go recommendation for campus expansion.

# Dependency graph

```text
Licensing / permissions ─────────────────────────────┐
                                                     v
OSM ────────┐                                  Reference bundles
Overture ───┼─> raw source records ─> normalize ─> canonical campus features
UPLB data ──┤                              |               |
Room TBA ───┤                              |               +--> feature/asset specs
IMS ────────┘                              |                         |
                                           |                         +--> Blender / AI asset pipeline
DEM/LiDAR ─> terrain source ─> local terrain model                    |
                                           |                         v
                                           +----> greybox generator -> Studio / Roblox place
Road/path canonical data ------------------+              |
                                                          v
                                              structural/spatial QA
                                                          |
Reference images + human review --------------------------+--> visual QA
                                                          |
Roblox streaming/performance constraints ----------------+--> performance QA
                                                          |
                                                          v
                                                  approved world revision
```

# Risks

| Risk | Probability | Impact | Mitigation | Fallback |
|---|---|---|---|---|
| insufficient current facade imagery | High | High | owned/authorized capture campaign; prioritize hero buildings | accurate massing + approximate facade with low confidence |
| OSM footprint error/staleness | Medium | High | Overture comparison + site/reference verification | placeholder geometry until verified |
| missing building heights | High | Medium | official/field dimensions, image ratios, Overture attrs | conservative level-based estimate marked approximate |
| restricted imagery accidentally ingested | Medium | High | rights enum + validator + gitignore + source register | remove artifact, regenerate from permitted sources |
| LiDAR unavailable | Medium | Medium | do not block POC; use 30 m DEM + local constraints | hand-refine vertical slice terrain |
| AI hallucinated architecture | High | High | AI limited to drafts/modules; visual QA | manual Blender correction |
| inconsistent art direction | Medium | High | shared kits/material palette/trim sheets | reject mismatched assets |
| photogrammetry too dense/noisy | High | Medium | use as reference mesh, retopologize | manual modeling from photos |
| Studio/Git drift | Medium | High | ownership matrix + source snapshot + manifests | regenerate replaceable layers; restore snapshot |
| world too heavy for mobile | Medium | High | streaming from day one, modular LOD, device gates | reduce detail/radius; split heavy interiors |
| too many unique textures | High | Medium | trim sheets/shared materials/512-first policy | rebake/atlas assets |
| terrain misalignment with buildings | Medium | High | one CRS, origin, vertical datum metadata, pad constraints | localized correction meshes/pads |
| source data changes upstream | High | Medium | pinned revisions/hashes, explicit refresh process | retain last validated canonical version |
| premature shared-data repository | Medium | Medium | wait until two consumers validate schema | keep app-neutral subset inside this repo |
| scope explosion / every interior | High | High | tiered interior priority, sector gates | exterior-only background buildings |

# Phase gates

A phase advances only when acceptance criteria are recorded in a validation report. “Looks okay in Studio” is not a phase gate.
