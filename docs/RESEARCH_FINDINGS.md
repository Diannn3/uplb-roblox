# Research Findings

_Status: architecture research, 2026-08-17. This document is technical research, not legal advice._

## 1. Executive findings

1. **The right target is a digital-twin-lite, not a survey-grade twin.** UPLB should be geographically coherent, recognizable, and maintainable, while explicitly labeling approximations. The largest quality gains will come from correct terrain, road/path geometry, building footprints/orientations, landmark silhouettes, vegetation character, and selected facades—not from fully modeling every interior.
2. **The project should be data-driven before it is asset-driven.** A canonical campus feature registry must own stable IDs, real-world coordinates, provenance, confidence, and links to Roblox/Blender assets. Models are representations of features; they are not the database.
3. **Use WGS84 for interchange and WGS84 / UTM zone 51N (EPSG:32651) for metric processing.** EPSG defines 32651 as a projected easting/northing CRS in metres covering 120°E–126°E, including the Philippines. [EPSG 32651](https://epsg.org/crs_32651/WGS-84-UTM-zone-51N.html), accessed 2026-08-17.
4. **OpenStreetMap and Overture should be compared, not treated as competitors.** OSM is locally editable and semantically rich; Overture's 2026-06-17 buildings release conflates OSM with multiple open/ML sources and prioritizes OSM, while exposing stable GERS-style IDs and building attributes. [Overture Buildings](https://docs.overturemaps.org/guides/buildings/), accessed 2026-08-17.
5. **Google Street View must not be the reconstruction ingestion layer.** Google's current Street View Static policy generally prohibits prefetching, indexing, storing, or caching content other than stated exceptions such as panorama IDs. The Map Tiles policy also places restrictions on non-visual uses. [Street View policy](https://developers.google.com/maps/documentation/streetview/policies), accessed 2026-08-17; [Map Tiles policy](https://developers.google.com/maps/documentation/tile/policies), accessed 2026-08-17.
6. **Roblox Studio MCP materially changes the AI workflow.** Roblox currently exposes MCP tools for script read/search/edit and for `generate_mesh`, `generate_material`, and `generate_procedural_model`. Persistent MCP output still needs an ownership/provenance rule; MCP is an execution channel, not source control. [Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp), accessed 2026-08-17.
7. **AI 3D generation should be used selectively.** Roblox Assistant can generate meshes and procedural models, use a selected Part as a bounding box, accept a reference image for Assistant mesh generation, and expose a triangle cap. These are excellent for first-pass props and constrained blockouts, but distinctive architecture must remain reference-driven and human-verified. [Roblox Assistant](https://create.roblox.com/docs/assistant/guide), accessed 2026-08-17.
8. **One streaming outdoor place is the default starting topology.** Roblox recommends instance streaming especially for large worlds because it improves join time and memory efficiency. Splitting into multiple places remains a later option for very heavy interiors or independently deployed zones. [Instance streaming](https://create.roblox.com/docs/workspace/streaming), accessed 2026-08-17; [Design for performance](https://create.roblox.com/docs/performance-optimization/design), accessed 2026-08-17.
9. **UPPETITE, Room TBA, and IMS already contain useful primitives.** We should reuse their concepts and licensed data, not their entire application architectures.

## 2. Immutable repository baseline

The research branch starts from `Diannn3/uplb-roblox` `feature/ai-context` at exact commit:

`66ad829819441447756bd0620e33023e11fc2d5f`

Parent scaffolding commit:

`34664dd8d4bfbf8414240eb2530947b985807753`

Tracked baseline:

- `.cursorrules`
- `.gitignore`
- `README.md`
- `default.project.json`
- `src/Client/MainClient.client.lua`
- `src/Server/MainServer.server.lua`
- `src/Shared/Constants.lua`

Rojo currently maps `src/Shared` to `ReplicatedStorage/Shared`, `src/Server` to `ServerScriptService/Server`, and `src/Client` to `StarterPlayer/StarterPlayerScripts/Client`. There is no package manager, generated-data layer, tests, CI, asset manifest, world source file, terrain pipeline, or build pipeline yet.

### Architectural deficiencies at baseline

- `Constants.LOCATIONS` conflates display names with what should become stable domain entities.
- No canonical geospatial source-of-truth or provenance model exists.
- World authoring ownership is undefined; current ignore rules exclude Roblox place/model files without specifying where persistent authored terrain should live.
- No distinction exists between hand-authored, generated, imported, and third-party assets.
- No validation or content budget enforcement exists.
- No contract links Roblox objects back to real-world feature IDs.

## 3. Related-project audit

### 3.1 UPPETITE / `Diannn3/kain-elbi`

Pinned research commit: `aab2d3dacbe47dd357b27fcbee12a10cbef226a2`.

Useful artifacts observed in the pinned tree include:

- `scripts/ingest_osm.py` — a small Overpass ingestion pattern with explicit User-Agent and GeoJSON output.
- `scripts/ingest_overture.py` — evidence that Overture is already part of the Los Baños data workflow.
- `scripts/lib/geo.py`, `identity.py`, `matching.py`, `normalize.py` — patterns for normalization and identity matching.
- `data/raw/osm-los-banos-food.geojson` and `data/raw/overture-los-banos-food.geojson` — evidence of source-separated raw data.
- `data/upstream/room-tba/` — provenance-preserving import boundary.
- `data/place_identity_registry.json`, `anchor_aliases.json`, `zones.json`, `route_matrix.json` — reusable concepts, but food-specific records should not become the campus twin schema.

Most important provenance finding: UPPETITE pins Room TBA's `src/generated/walk-graph.json` at `feb008212af6b54d3344f44c4a33672b50983fcc`, SHA-256 `b8c57e6d04276ca55d5ba8a93d7ef0d5f99c9d83c7d783e4e0f4487a18127b5e`, recording 1,014 nodes and 1,468 edges. Its notice correctly separates Room TBA MIT application licensing from the OSM-derived path network's ODbL obligations. It also states that UPPETITE's `anchors.json` is separately sourced and must not be attributed to Room TBA.

**Reuse:** ingest patterns, normalization concepts, provenance discipline, and the pinned pedestrian graph as an optional input layer.

**Do not reuse blindly:** food-place schema, application UI, routing cache semantics, or any data whose source/redistribution terms are unclear.

### 3.2 IMS / `Diannn3/ims-app`

Pinned research commit: `a922d74f881d97075d61ac9277c6927efdabc21e`.

The IMS map spec is particularly valuable because it explicitly says the current geometry comes from orientation posters and is **not architectural**, so every generated geometry object carries `verificationStatus: needs-site-verification`. It separates:

- space geometry: room/facility shape and identity;
- routing graph: corridors, doors, stairs, entrances, and weighted edges;
- stable IDs from display names;
- generated SVG presentation from structured runtime data.

The routing spec uses a small weighted graph, A* routing, cross-floor stair connectors, and separately modeled dynamic closures. These are strong domain patterns for future Roblox interiors.

**Reuse:** stable indoor IDs, explicit verification state, space-vs-route graph separation, floor transitions, door/entrance semantics.

**Do not treat as metric truth:** the current 1200×760 floor canvas is deliberately non-geographic and site-unverified.

### 3.3 Room TBA / `uplbtools/room-tba`

Current audit pin: `ff7179c9f7604106720ce587b260ceb7caa9bd4c` (2026-08-15 current main during research).

Application code is MIT, but that license does not override embedded/open-data licenses. The UPPETITE provenance copy demonstrates the correct handling: OSM-derived network data retains ODbL obligations.

**Reuse:** path graph data where the layer's license permits it; naming/alias conventions where independently verifiable; map-engineering lessons.

**Do not infer:** that all Room TBA content is MIT merely because the code repository has an MIT `LICENSE`.

## 4. Data-source findings

### OpenStreetMap

Recommended role: primary editable semantic layer for paths, roads, entrances, amenities, names, and community-corrected building footprints. OSM data is ODbL and requires attribution. [OSM copyright](https://www.openstreetmap.org/copyright), accessed 2026-08-17.

Strengths:

- strong campus-specific community editability;
- feature tags and relations;
- direct correction path when local knowledge finds errors;
- compatible with Room TBA's existing path-network lineage.

Weaknesses:

- uneven building height/levels/facade completeness;
- mapped geometry is not automatically survey-grade;
- historical/stale features must be visually/site verified.

### Overture Maps

Recommended role: independent footprint/completeness comparator and possible GERS-linked enrichment layer. The 2026-06-17 buildings dataset is GeoParquet and combines OSM with Esri Community Maps, Google Open Buildings, Microsoft and other sources; OSM is prioritized in conflation. [Buildings guide](https://docs.overturemaps.org/guides/buildings/), accessed 2026-08-17.

The transportation theme is a global routable segment/connector model built from OSM plus other sources and is distributed as GeoParquet. [Transportation guide](https://docs.overturemaps.org/guides/transportation/), accessed 2026-08-17.

Recommendation: keep raw OSM and Overture outputs separate, normalize into candidate features, then conflate into our own canonical feature records with source-level provenance. Never overwrite OSM-derived identity simply because Overture has a footprint.

### Geoportal Philippines / NAMRIA

Geoportal exposes government layers and WMS access, but downloadability and conditions vary by data owner. Its current download agreement includes purpose limitations and attribution/copy-of-output terms. Therefore, data is **conditional**, not automatically open for redistribution in a public Roblox repository. [Geoportal Philippines](https://geoportal.gov.ph/), accessed 2026-08-17.

Recommendation: use Geoportal first as discovery and metadata infrastructure. Only ingest a layer after recording its explicit dataset-level terms.

### LiPAD / UP DREAM

LiPAD advertises DEMs, DTMs, orthophotos and classified LAZ from Phil-LiDAR. Access and redistribution must be checked for the exact requested product and user category. [LiPAD](https://lipad.dream.upd.edu.ph/), accessed 2026-08-17.

Recommendation: create a permission/data-request task for Los Baños coverage. Do not block the proof of concept on LiDAR.

### Baseline DEM candidates

- NASA SRTM GL1: 30 m near-global elevation, useful as a free coarse baseline. [NASA LP DAAC](https://www.earthdata.nasa.gov/centers/lp-daac), accessed 2026-08-17.
- OpenTopography: API aggregator for SRTM, NASADEM, COP30 and others; each underlying dataset retains its own terms. [OpenTopography developers](https://opentopography.org/developers), accessed 2026-08-17.
- Copernicus DEM GLO-30: 30 m DSM with a free license and required source notices, but 2026 service-access changes mean dataset licensing and a specific endpoint's access controls must be treated separately. [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), accessed 2026-08-17.

A 30 m DEM is insufficient for curb-level accuracy or subtle building pads. It is acceptable for macro relief, then must be locally corrected around roads/vertical-slice landmarks from authorized higher-resolution evidence.

## 5. Street-level imagery findings

### Google Street View

**Decision: exclude from automated reconstruction ingestion.** Google's current Street View Static policy states that prefetching, indexing, storing, or caching is generally prohibited, with narrow exceptions such as panorama IDs. [Policy](https://developers.google.com/maps/documentation/streetview/policies), accessed 2026-08-17.

Use Google only as a transient human visual reference when consistent with its current terms. Do not bulk download, archive, photogrammetrically reconstruct, train against, or build a scraping pipeline around Google imagery.

### Mapillary

Mapillary currently offers API-based access, and its help center describes imagery as CC-BY-SA with attribution requirements while separately pointing users to Terms/Commercial Terms for use. [License help](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data), accessed 2026-08-17; [API help](https://help.mapillary.com/hc/en-us/articles/360010234680-Accessing-imagery-and-data-through-the-Mapillary-API), accessed 2026-08-17.

Recommendation: use first for **coverage discovery and reference indexing**, then perform an explicit use/derivative review before automated 3D reconstruction from imagery.

### KartaView

KartaView documents APIs covering photos, sequences and 3D-related data. Its current terms state CC BY-SA 4.0 for street images and 3D spatial data and MIT for software. [Docs](https://kartaview.org/doc/), [Terms](https://kartaview.org/terms), accessed 2026-08-17.

Recommendation: strong candidate for a legal street-level reference layer, subject to preserving attribution/share-alike obligations and verifying actual UPLB coverage.

### Own captures

Best long-term reference source for distinctive UPLB buildings: user/team-captured photographs from public/authorized viewpoints, with a capture manifest containing date, photographer, consent/permission state, GPS if intentionally recorded, facade side, and redistribution permission. Do not enter restricted areas or capture sensitive material.

## 6. 3D and reconstruction tooling

### Blender / BlenderGIS

Blender is the recommended production DCC. BlenderGIS can import common GIS formats, GeoTIFF DEM, OSM XML, georeference scenes, and generate terrain; its repository is GPL-3.0 and released v2.2.15 in Dec 2025. [BlenderGIS](https://github.com/domlysz/BlenderGIS), accessed 2026-08-17.

Use BlenderGIS as a productivity tool, not as the canonical database. A Blender scene can always be regenerated/re-aligned from canonical feature data.

### Meshroom / AliceVision

Meshroom is MPL-2.0 and its modern plugin architecture supports photogrammetry and other 3D pipelines. The 2025.1 release added a broader plugin system and remains suitable for reference reconstruction. [Meshroom](https://github.com/alicevision/Meshroom), accessed 2026-08-17.

Use photogrammetry primarily to obtain high-resolution **reference meshes** and distinctive small landmarks. Raw reconstructions are usually too dense/noisy for direct Roblox shipping.

### COLMAP

COLMAP remains an actively documented SfM/MVS system; its 2026 documentation identifies a new BSD license and a current development line. [COLMAP license](https://colmap.github.io/license.html), accessed 2026-08-17.

Use as a CLI-friendly alternative when scripted SfM matters more than Meshroom's visual pipeline.

## 7. Roblox platform findings

### Studio MCP

Current official MCP tools include script read/search/grep/multi-edit and AI content generation (`generate_mesh`, `generate_material`, `generate_procedural_model`). [MCP docs](https://create.roblox.com/docs/studio/mcp), accessed 2026-08-17.

Important boundary: the MCP documentation's `generate_mesh` tool is documented as text-prompt generation. Do not assume every Assistant UI image-conditioned capability is exposed identically through MCP.

### Assistant generation

Assistant can create/modify objects, insert Creator Store assets, generate materials, meshes and procedural models. Its mesh workflow supports a selected Part as a bounding box and lets a user specify a triangle cap; Assistant also documents reference-image input for mesh generation. [Assistant guide](https://create.roblox.com/docs/assistant/guide), accessed 2026-08-17.

Use cases:

- generic campus prop blockouts;
- quick bounding-box-constrained drafts;
- procedural repetitive assets;
- material ideation.

Not trusted by default for:

- exact landmark architecture;
- licensed logo/sign reproduction;
- dimension-critical geometry;
- final collision meshes.

### Mesh and texture constraints

Roblox states an individual custom mesh cannot exceed 20,000 triangles. [General specifications](https://create.roblox.com/docs/art/modeling/specifications), accessed 2026-08-17.

Roblox supports up to 4096×4096 texture uploads, but recommends smaller resolutions based on asset size (for example 256 for small and 512 for medium objects) to improve memory use. [Texture specifications](https://create.roblox.com/docs/art/modeling/texture-specifications), accessed 2026-08-17.

These are platform capabilities, not a license to ship 20k-triangle/4K assets everywhere. Our project budgets are intentionally lower.

### Streaming

Roblox says instance streaming dynamically loads/unloads Workspace content and can improve join time, memory efficiency and performance, and recommends it especially for larger worlds. [Streaming](https://create.roblox.com/docs/workspace/streaming), accessed 2026-08-17.

Conclusion: UPLB's outdoor campus should be designed around streaming from the first proof of concept.

## 8. Comparable-project lessons

The most transferable pattern from GIS/digital-twin work is not a specific repo: it is **separation of geospatial truth, derived geometry, and presentation assets**. BlenderGIS demonstrates a GIS→DCC bridge; Overture demonstrates multi-source conflation with source attribution; IMS demonstrates semantic geometry separated from routing; Room TBA/UPPETITE demonstrate provenance-preserving campus routing imports.

For this project, copying a monolithic “OSM-to-game” generator would be less useful than combining these patterns with Roblox-specific streaming and asset budgets.

## 9. Research limitations

The 2026-08-17 network-enabled harness run fetched the OSM AOI successfully and recorded 10,319 elements (7,725 building-tagged, 2,524 highways, 70 waterways, 814 named) plus a SHA-256 in `research/results/osm_overture_comparison.json`. The installed Overture client failed while resolving its STAC catalog with HTTP 404, so no Overture coverage conclusion is drawn; the result records this as a provider failure and the next retry must use a verified current client/catalog or an explicitly documented direct cloud-data path.

This provider failure does **not** change the architecture decision; it creates a concrete retry task for a verified current Overture client/catalog or documented direct cloud-data path.
