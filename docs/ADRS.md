# Architecture Decision Records

All ADRs are **Proposed** until the user approves the master plan. Evidence access date: 2026-08-17.

## ADR-001 — Canonical geospatial format

**Status:** Proposed  
**Decision:** Source-controlled normalized GeoJSON for spatial features plus JSON manifests for non-spatial metadata; generate GeoPackage/GeoParquet/Luau as derived artifacts.  
**Why:** human/AI readable, diffable, portable, sufficient for campus scale, avoids binary canonical database drift.  
**Alternatives:** GeoPackage canonical (strong GIS tooling, weak diffs); PostGIS (overkill/server dependency); GeoParquet canonical (excellent analytics, less hand-reviewable).  
**Consequence:** validation/generation tooling must enforce schema and deterministic ordering.

## ADR-002 — Coordinate system

**Status:** Proposed  
**Decision:** WGS84/EPSG:4326 interchange → EPSG:32651 metric processing → local UPLB metres.  
**Evidence:** EPSG 32651 is metre-based UTM 51N covering 120°E–126°E including the Philippines: https://epsg.org/crs_32651/WGS-84-UTM-zone-51N.html.  
**Alternative:** stay in lat/lon (poor metric operations); Philippine legacy/local CRS (potentially appropriate for authoritative agency data but adds transformations and must follow actual source CRS).  
**Consequence:** every source CRS must be recorded and transformed explicitly.

## ADR-003 — World scale

**Status:** Proposed / validate in vertical slice  
**Decision:** initial `3.5714286 studs/m` (0.28 m/stud) configurable project scale.  
**Why:** establishes a human-scale convention while preserving real metre data separately.  
**Alternative:** 1 stud/m (compact but avatar/building scale awkward); 4 studs/m (simple but arbitrary).  
**Consequence:** never bake Roblox studs into canonical GIS. One config change can regenerate positions.

## ADR-004 — Terrain source

**Status:** Proposed  
**Decision:** legal 30 m DEM baseline (SRTM/NASADEM/COP30 candidate) + local constraints/refinement; request LiPAD/authorized higher-res data in parallel.  
**Why:** proof of concept must not wait for restricted LiDAR; 30 m alone is too coarse for roads/building pads.  
**Consequence:** terrain confidence varies by scale and must be recorded.

## ADR-005 — Building source

**Status:** Proposed  
**Decision:** property-level conflation: verified/official evidence when authorized, locally verified OSM as strong semantic layer, Overture as independent completeness/footprint comparator, manual verification for hero buildings.  
**Evidence:** Overture prioritizes OSM in building conflation and includes ML/open sources: https://docs.overturemaps.org/guides/buildings/.  
**Consequence:** no “single magic dataset.”

## ADR-006 — Street-level imagery

**Status:** Proposed  
**Decision:** Google excluded from automated storage/reconstruction; Mapillary/KartaView and owned captures considered under explicit rights records.  
**Evidence:** Google Street View Static current caching restrictions: https://developers.google.com/maps/documentation/streetview/policies.  
**Consequence:** building reference bundles must carry ingestion permission status.

## ADR-007 — AI model generation

**Status:** Proposed  
**Decision:** AI for drafts, generic props, constrained subcomponents, and procedural candidates; distinctive architecture requires modular/reference-driven human QA.  
**Evidence:** Roblox Assistant and Studio MCP generation capabilities: https://create.roblox.com/docs/assistant/guide and https://create.roblox.com/docs/studio/mcp.  
**Consequence:** generated output is never automatically “verified.”

## ADR-008 — Blender role

**Status:** Proposed  
**Decision:** Blender is the primary production DCC and automation host for modular architecture, road sweeps, retopology, UV/material prep and mesh export. BlenderGIS is optional support, not canonical truth.  
**Consequence:** store scripts/specs so Blender work can be repeated; source `.blend` enters LFS only after asset workflow approval.

## ADR-009 — Roblox world architecture

**Status:** Proposed  
**Decision:** one streaming outdoor place first; separate places only for measured heavy-interior/deployment needs.  
**Evidence:** Roblox recommends streaming for large worlds and discusses multiple-place tradeoffs: https://create.roblox.com/docs/performance-optimization/design.  
**Consequence:** outdoor traversal stays seamless.

## ADR-010 — Streaming strategy

**Status:** Proposed  
**Decision:** `StreamingEnabled` from first vertical slice; streaming-safe scripts; minimize persistent world models; profile radius settings rather than choosing them by guess.  
**Evidence:** https://create.roblox.com/docs/workspace/streaming.  
**Consequence:** Workspace existence cannot be used as canonical map data.

## ADR-011 — Asset versioning

**Status:** Proposed  
**Decision:** Git for code/data/specs; generated caches ignored; Git LFS later for accepted Blender sources and designated Studio source snapshots; Roblox asset IDs tracked in manifests.  
**Alternative:** cloud-only Team Create (insufficient reproducibility); commit every binary to normal Git (repository bloat).  
**Consequence:** current ignore rules stay conservative until LFS is configured.

## ADR-012 — AI/Studio MCP workflow

**Status:** Proposed  
**Decision:** MCP is an execution interface. Persistent MCP outputs must either be reproducible from Git specs or promoted into the designated Studio source snapshot + manifest.  
**Evidence:** current MCP tool surface: https://create.roblox.com/docs/studio/mcp.  
**Consequence:** no untracked “AI magic” in production Studio.

## ADR-013 — Shared UPLB dataset

**Status:** Proposed  
**Decision:** design app-neutral schemas now, but postpone creation of a standalone `uplb-geodata` repository until the Roblox vertical slice and at least one other consumer validate the contract.  
**Why:** avoids premature platform work and accidental license mixing while preserving a clean extraction path.  
**Consequence:** license-compatible canonical data must remain separable from Roblox-only manifests.
