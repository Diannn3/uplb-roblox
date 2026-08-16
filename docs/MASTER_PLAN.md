# UPLB Roblox Master Architecture Plan

**Research date:** 2026-08-17  
**Base:** `feature/ai-context` @ `66ad829819441447756bd0620e33023e11fc2d5f`  
**Research branch:** `research/uplb-master-execution-plan`  
**Scope:** research, architecture, reproducibility and execution plan only; no production world systems are implemented here.

## Executive recommendation

Build UPLB as a **data-driven digital-twin-lite**. Treat WGS84/UTM geospatial data, provenance and confidence as the source of truth; generate a deterministic campus greybox from OSM/Overture plus legal terrain data; use Blender for modular production assets and constrained photogrammetry/reference workflows; use Roblox Studio MCP/Assistant for disposable blockouts, procedural candidates and low-stakes props rather than as an authority on real architecture; run the outdoor campus initially as one streaming Roblox place; and require every persistent Studio object to be either reproducible from Git specs or captured in a versioned authored-world source plus manifest. Human/site verification remains mandatory where sources are approximate.

## Product fidelity decision

### Options considered

| Level | Description | Benefit | Cost/risk |
|---|---|---|---|
| A — stylized | recognizable but freely rearranged/simplified | fastest | loses navigational/digital-twin value |
| B — geographic | correct-ish positions/roads, simplified architecture | moderate | landmarks may feel generic |
| **C — digital-twin-lite** | metric geographic backbone, recognizable exterior architecture, selective interiors | **best balance** | requires disciplined source/asset pipeline |
| D — near digital twin | broad survey-grade detail/interiors | highest fidelity | unrealistic student-scale data/survey/production burden |

**Recommendation: C.**

### Initial measurable fidelity targets

These are project acceptance targets and must be tightened/relaxed based on source evidence:

- verified hero-building placement: target ≤2 m from approved canonical reference;
- ordinary building placement: target ≤3–5 m until better data exists;
- verified road/path centerline in vertical slice: target ≤2 m where current source permits;
- hero footprint/orientation: target shape/orientation discrepancy documented and visually checked; use metric IoU once live data comparison runs;
- building height: no numeric “verified” claim without source; approximate estimates must be labeled;
- facade: recognizable repeated-bay count, major openings, roof silhouette and landmark features for hero assets;
- interiors: no metric accuracy claim until calibrated/authorized source or site measurements exist.

Numerical CRS precision is much higher than these tolerances; physical source accuracy is the limiting factor.

## Master architecture

```text
                    RIGHTS / SOURCE REGISTER
                              |
              +---------------+----------------+
              |                                |
      public/open geodata              authorized references
   OSM / Overture / DEMs          UPLB data / own photos / LiDAR
              |                                |
              +------------ raw records -------+
                              |
                       normalize/conflate
                              |
                  CANONICAL CAMPUS FEATURES
               GeoJSON + JSON + provenance
                              |
             +----------------+-------------------+
             |                |                   |
          terrain         roads/paths          buildings
             |                |                   |
             +--------- deterministic greybox ----+
                              |
               asset/building specifications
                    |                     |
                 Blender            Roblox AI/MCP
              production kit        drafts/props/tools
                    |                     |
                    +----- asset manifests+
                              |
                      ROBLOX STUDIO WORLD
                       StreamingEnabled
                              |
       +----------------------+----------------------+
       |                      |                      |
 spatial/source QA      visual human QA       device/perf QA
       +----------------------+----------------------+
                              |
                    approved world revision
```

## Canonical data stack

- **EPSG:4326**: source/interchange latitude-longitude.
- **EPSG:32651**: metric geospatial processing.
- **Local UPLB metres**: UTM minus fixed origin.
- **Roblox studs**: generated presentation coordinate only.
- **GeoJSON**: canonical spatial records.
- **JSON**: provenance, asset, building, QA and config records.
- **Generated GeoPackage/GeoParquet**: analytics/tooling convenience only.
- **Generated Luau**: runtime lookup only; never hand-edited.

See `GEOSPATIAL_ARCHITECTURE.md`.

## Data acquisition strategy

1. Query OSM for campus buildings/roads/paths/waterways/entrances.
2. Query the current pinned Overture release for buildings/transport and compare geometry/attributes.
3. Audit UPLB official/public resources and request authoritative GIS/building metadata where available.
4. Discover Geoportal/NAMRIA and LiPAD products; ingest only after exact rights are documented.
5. Use a legal 30 m DEM to unblock macro terrain; refine local terrain with authorized evidence.
6. Use Room TBA's OSM-derived walk graph as an optional licensed upstream layer, preserving ODbL.
7. Reuse UPPETITE ingest/provenance patterns and IMS indoor semantics rather than copying application-specific schemas.
8. Build owned/authorized photo reference bundles for hero buildings.

## Street-view strategy

### Google

No scraping, bulk caching, archive, computer-vision ingestion, or photogrammetry corpus. Current Street View Static policy generally prohibits prefetch/index/store/cache except stated exceptions. Human visual use must remain within current platform terms. See `DATA_GOVERNANCE_AND_LICENSING.md`.

### Mapillary/KartaView

Use API/coverage tools to discover available sequences. Before automated derivatives, record per-source rights and terms. KartaView's current terms make it a particularly promising open street/3D reference candidate; Mapillary remains useful but must be handled with its Terms/Commercial Terms in addition to help-center licensing statements.

### Best long-term source

Owned team captures from authorized public viewpoints, indexed and rights-cleared.

## Terrain recommendation

Hybrid:

- legal DEM → macro Roblox Terrain;
- verified roads/building pads constrain local grade;
- meshes/parts handle curbs, retaining walls, stairs, bridges and hardscape;
- authorized high-res LiDAR/DTM replaces/refines baseline when available.

## 3D production recommendation

- procedural infrastructure from GIS/specs;
- reusable campus prop/material/architecture kits;
- Blender modular hero buildings;
- AI-generated generic props/subcomponents after QA;
- photogrammetry for reference/high-detail small landmarks, then retopology;
- Creator Store only through quarantine/security/style/budget review.

## Roblox architecture recommendation

One streaming outdoor campus place. Keep runtime code modular and small, canonical map data outside Workspace, and scripts tolerant of streamed-out instances. Separate heavy interiors into additional places only when profiling proves necessary.

Persistent Studio state follows the ownership matrix in `ROBLOX_ARCHITECTURE.md`.

## Recommended proof of concept

**Vertical Slice v1:** Oblation/Freedom Park/Baker Hall landmark cluster plus one standard building and a walkable road/path loop.

It must prove:

- EPSG transform and real placement;
- baseline terrain/refinement;
- roads/paths;
- vegetation;
- one normal building;
- one hero landmark/building;
- one AI-generated prop;
- one vetted library/reusable prop;
- streaming;
- source/spatial/asset validation;
- visual reference QA;
- representative mobile performance.

If this slice cannot be regenerated after a canonical-data change, the architecture is not ready to scale.

## Interior strategy

Tiers:

1. exterior only;
2. lobby/public shell;
3. major navigable interior;
4. full/select flagship interior.

The Math Building is a strong first detailed-interior candidate because IMS already has stable room IDs, floors and route-graph semantics. Its current geometry is explicitly poster-derived and non-geographic, so metric use is blocked on calibration/site or authorized plan evidence.

## Version control recommendation

Research phase keeps Roblox binary/XML world formats ignored. After Vertical Slice v1 proves the workflow:

- Git: code/data/specs/docs;
- Git LFS: accepted Blender sources and designated Studio source snapshots;
- generated bulk/raw/cache: ignored;
- Roblox cloud assets: IDs + hashes/provenance in Git manifests;
- MCP output: never source-of-truth by itself.

## Art/performance direction

Do not chase photorealism. Optimize for **recognizable silhouettes, materials, tropical campus atmosphere and scale**.

Hard platform mesh rule: ≤20,000 triangles per individual mesh. Internal project budgets are intentionally below that for most assets. Prefer shared trim sheets/materials and 256–512 textures; reserve 1024 for hero needs validated by profiling. Instance streaming is mandatory from the proof of concept.

## Existing-project reuse decision

### UPPETITE

Reuse OSM/Overture ingest patterns, normalization concepts, Room TBA provenance boundary and licensed upstream data where useful. Do not inherit food-specific schema.

### Room TBA

Reuse/pin the pedestrian graph subject to ODbL and independently validate current paths. MIT application licensing does not override OSM data obligations.

### IMS

Reuse stable indoor IDs, space/route separation, floor-transition semantics and verification discipline. Do not treat its current poster coordinate canvas as metric truth.

### Shared UPLB geodata

Design for extraction but postpone a standalone repository until the vertical slice and another consumer validate the schema.

## AI division of labor

| Role | Best use |
|---|---|
| Codex | repo/data pipelines, tests, Blender Python, Luau, manifests, validation |
| Codex + Studio MCP | Studio inspection, disposable blockouts, procedural/AI prop candidates, scoped edits/playtests |
| ChatGPT / vision-capable analysis | research synthesis, reference classification, visual discrepancy review, specs |
| Antigravity or other MCP client | repetitive Studio tasks when connected to the same approved MCP workflow |
| Roblox Assistant | Studio-native mesh/material/procedural generation and ideation |
| Human | source permission, site capture, landmark judgment, final visual approval |

## Repository target structure

```text
docs/                         # architecture + operating docs
research/                     # research manifests, fixtures, comparison harness
research/contracts/           # draft schemas
src/                          # Roblox Luau (existing; production changes later)
data/                         # future canonical/raw/processed geodata
  raw/                        # ignored/manifested downloads
  canonical/                  # Git-tracked GeoJSON/JSON truth
  generated/                  # derived outputs
references/                   # rights-aware reference bundles
tools/
  geodata/
  worldgen/
  blender/
  validation/
assets/
  manifests/                  # source controlled
  source/                     # future LFS where approved
  generated/                  # ignored/rebuildable
world/
  source/                     # future designated Studio source snapshot/LFS
  generated/                  # replaceable world outputs
```

Do not create empty production directories until the corresponding implementation phase begins.

## Risk and cost posture

The core pipeline can remain mostly free/open. Biggest risks are not software price: they are source rights, missing current imagery/dimensions, scope expansion, inconsistent AI output, and mobile world cost. Detailed register and mitigations are in `ROADMAP.md` and `DATA_GOVERNANCE_AND_LICENSING.md`.

## Requirement traceability — original 48-section brief

| # | Requirement | Primary document |
|---:|---|---|
| 1 | orient current project | `RESEARCH_FINDINGS.md` §2 |
| 2 | define product/fidelity | this document: Product fidelity decision |
| 3 | canonical campus data model | `GEOSPATIAL_ARCHITECTURE.md` §5 |
| 4 | geospatial coordinate system | `GEOSPATIAL_ARCHITECTURE.md` §§1–4 |
| 5 | data acquisition master plan | this document: Data acquisition strategy; `RESEARCH_FINDINGS.md` §4 |
| 6 | do not blindly scrape Google | this document: Street-view strategy; `DATA_GOVERNANCE_AND_LICENSING.md` §3 |
| 7 | campus reference database | `DATA_GOVERNANCE_AND_LICENSING.md` §4 |
| 8 | terrain generation | `GEOSPATIAL_ARCHITECTURE.md` §9 |
| 9 | procedural campus greybox | `ROBLOX_ARCHITECTURE.md` §12; `ROADMAP.md` Phase 2 |
| 10 | Blender GIS pipeline | `ASSET_PIPELINE.md` §5; `RESEARCH_FINDINGS.md` §6 |
| 11 | photogrammetry/reconstruction | `ASSET_PIPELINE.md` §8 |
| 12 | AI-generated 3D pipeline | `ASSET_PIPELINE.md` §6 |
| 13 | what AI should generate | `ASSET_PIPELINE.md` §2 |
| 14 | Creator Store/libraries | `ASSET_PIPELINE.md` §7 |
| 15 | AI→Blender | `ASSET_PIPELINE.md` §5 |
| 16 | reference-image-to-building | `ASSET_PIPELINE.md` §4 |
| 17 | building kit system | `ASSET_PIPELINE.md` §§2,12 |
| 18 | existing-project reuse | `RESEARCH_FINDINGS.md` §3; this document |
| 19 | UPLB open-data repository | `DATA_GOVERNANCE_AND_LICENSING.md` §6 |
| 20 | Roblox software architecture | `ROBLOX_ARCHITECTURE.md` §§3–6 |
| 21 | world architecture | `ROBLOX_ARCHITECTURE.md` §1 |
| 22 | streaming + LOD | `ROBLOX_ARCHITECTURE.md` §§9–11; `ASSET_PIPELINE.md` §10 |
| 23 | vegetation | `GEOSPATIAL_ARCHITECTURE.md` §11 |
| 24 | road + walkway generator | `GEOSPATIAL_ARCHITECTURE.md` §10 |
| 25 | interiors | this document: Interior strategy; `ROADMAP.md` Phase 6 |
| 26 | gameplay vs digital twin | `ROBLOX_ARCHITECTURE.md` §13 |
| 27 | automation pipeline | `AUTOMATION_AND_VALIDATION.md` §§1–3 |
| 28 | AI agent architecture | `AUTOMATION_AND_VALIDATION.md` §11 |
| 29 | MCP-first workflow | `ROBLOX_ARCHITECTURE.md` §7 |
| 30 | version control for 3D | `ROBLOX_ARCHITECTURE.md` §§2,8 |
| 31 | validation system | `AUTOMATION_AND_VALIDATION.md` §§4–9 |
| 32 | confidence-based reconstruction | `AUTOMATION_AND_VALIDATION.md` §4 |
| 33 | building production tracker | `AUTOMATION_AND_VALIDATION.md` §10 |
| 34 | campus reconstruction priority | `ROADMAP.md` Phases 5–7 |
| 35 | first proof of concept | this document: Recommended proof of concept |
| 36 | legal/licensing matrix | `DATA_GOVERNANCE_AND_LICENSING.md` §3 |
| 37 | cost analysis | `DATA_GOVERNANCE_AND_LICENSING.md` §8 |
| 38 | similar projects | `RESEARCH_FINDINGS.md` §8 |
| 39 | current 2026 tooling | `RESEARCH_FINDINGS.md` §§4–7 |
| 40 | risk register | `ROADMAP.md` Risks |
| 41 | ADRs | `ADRS.md` ADR-001–ADR-013 |
| 42 | execution roadmap | `ROADMAP.md` Phases 0–10 |
| 43 | dependency graph | `ROADMAP.md` Dependency graph |
| 44 | final repository structure | this document: Repository target structure |
| 45 | first 20 actions | `ROADMAP.md` First 20 implementation tasks |
| 46 | Codex automation labels | `AUTOMATION_AND_VALIDATION.md` §11; `ROADMAP.md` task labels |
| 47 | final deliverables A–Z | documentation suite listed below |
| 48 | create plan documents in repo | this committed documentation suite |

## Documentation suite

- [`RESEARCH_FINDINGS.md`](RESEARCH_FINDINGS.md)
- [`GEOSPATIAL_ARCHITECTURE.md`](GEOSPATIAL_ARCHITECTURE.md)
- [`DATA_GOVERNANCE_AND_LICENSING.md`](DATA_GOVERNANCE_AND_LICENSING.md)
- [`ASSET_PIPELINE.md`](ASSET_PIPELINE.md)
- [`ROBLOX_ARCHITECTURE.md`](ROBLOX_ARCHITECTURE.md)
- [`AUTOMATION_AND_VALIDATION.md`](AUTOMATION_AND_VALIDATION.md)
- [`ADRS.md`](ADRS.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`../research/README.md`](../research/README.md)

## What you should do tomorrow

1. Review `docs/EVIDENCE_GATE_REPORT.md`: OSM is pinned, while the official Overture client returned a STAC 404 and the bounded direct-cloud probe timed out. This is a provider-access warning, not a coverage conclusion.
2. Review the three permission-request drafts in `docs/PERMISSION_REQUEST_TEMPLATES.md`; nothing is sent without human approval.
3. Decide whether the proposed **Digital-twin-lite / one streaming outdoor place / EPSG:32651 / GeoJSON+JSON canonical** ADR set is approved for production use.
4. Review the generated canonical feature registry and the Oblation/Freedom Park/Baker Hall vertical-slice export before any Roblox greybox work.

## What Codex should implement first after approval

Phase 1's deterministic CRS, canonical contracts, OSM ingest, Overture adapter, provenance records, review queue, and generated Luau handoff are implemented locally on the feature branch. The first visible Roblox output should come only after the conditional evidence gate and canonical-data review are accepted.
