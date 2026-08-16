# Automation and Validation Architecture

## 1. Goal

Automation exists to make the campus **repeatable and auditable**, not to remove human judgment. The desired steady-state loop is:

```text
permitted source data
  -> normalized candidates
  -> conflation/review
  -> canonical campus features
  -> generated building/road/terrain specs
  -> Blender/Studio generation
  -> Roblox import/placement
  -> structural + spatial + performance + visual QA
  -> human approval
  -> promoted asset/world revision
```

No automated step is allowed to turn low-confidence evidence into high-confidence geometry without recording the change and reviewer.

## 2. Proposed commands

These are contracts for later implementation, not commands added in this research phase.

```text
uplb-research verify-sources
uplb-data fetch-osm
uplb-data fetch-overture
uplb-data normalize
uplb-data conflate
uplb-data validate
uplb-world generate-greybox
uplb-world generate-terrain-preview
uplb-world generate-roads
uplb-world generate-building-masses
uplb-assets validate
uplb-assets export-blender
uplb-roblox generate-runtime-data
uplb-roblox validate-place
uplb-qa compare-reference
```

A future `justfile`, `mise` tasks, Python CLI, or equivalent may expose them. Do not add a task runner until the first two implementation phases prove the interfaces.

## 3. Pipeline contracts

### Canonical feature

Defined by `research/contracts/campus-feature.schema.json`.

### Provenance record

Defined by `research/contracts/provenance-record.schema.json`.

### Building production spec

Defined by `research/contracts/building-spec.schema.json`.

### Asset manifest

Required fields:

- `assetId`
- `featureIds`
- `sourceSpecHash`
- `productionMethod`
- `sourceFiles`
- `robloxAssetIds`
- `triangleCounts`
- `textureFilesAndSizes`
- `collisionStrategy`
- `lodStrategy`
- `rightsRecords`
- `verificationStatus`
- `approvedBy`
- `approvedAt`

### Validation report

Required sections:

- input revisions/hashes;
- schema checks;
- spatial checks;
- source/license checks;
- Roblox object checks;
- performance measurements;
- visual discrepancies;
- unresolved blockers;
- pass/fail decision.

### AI building handoff

A handoff folder should contain:

```text
building-spec.json
reference-index.json
asset-manifest.json         # once assets exist
open-questions.md
qa-report.json
qa-notes.md
```

An AI agent receiving the bundle must be able to continue without rereading unrelated project history.

## 4. Confidence model

Use per-property confidence rather than one vague building score.

Suggested values:

- `authoritative` — official/survey evidence whose terms and scope are verified;
- `verified-high` — independently checked against current site evidence;
- `medium` — credible source but not physically verified;
- `approximate` — inference suitable for greybox/background only;
- `unknown` — no reliable evidence;
- `conflicting` — sources disagree and require review.

Example:

```json
{
  "position": "verified-high",
  "footprint": "medium",
  "height": "approximate",
  "facade": "verified-high",
  "interior": "unknown"
}
```

Promotion rules:

- `unknown/conflicting` dimension-critical values block a `verified` status;
- approximate geometry may ship only if its presentation does not imply survey accuracy;
- a human review cannot erase source uncertainty; it can only record what was visually/site verified.

## 5. Spatial validation

### Automated

- all canonical geometries valid GeoJSON;
- IDs unique and stable;
- coordinates inside expected research/campus envelope unless explicitly external;
- building polygon is valid and non-self-intersecting;
- entrance point within tolerance of its building/edge;
- road/path network has no accidental disconnected fragments in required traversal graph;
- generated local coordinates equal the deterministic CRS transform;
- forward/inverse transform round-trip passes numeric tolerance;
- duplicate/near-duplicate source features flagged;
- generated world placement compared to canonical centroid/orientation;
- unexpected overlaps/intersections reported.

### Human/site

- actual entrance exists and is public/usable;
- path is physically walkable;
- building facade/silhouette/current condition matches;
- stairs/retaining walls/grade make sense;
- accessibility details are separately verified.

## 6. Data/licensing validation

Fail a production build when:

- retained file lacks source record;
- source rights are `uncertain`, `permission-required`, or `restricted-do-not-ingest` but the file is in a redistributable asset path;
- required attribution is missing from attribution manifest;
- raw restricted/proprietary imagery appears in Git;
- an OSM-derived dataset is relabeled only as MIT;
- a source hash/revision changed without review.

Specific hard rule: **Google Street View/Map Tiles imagery must never appear in `references/`, `research/raw/`, Blender source, photogrammetry input, or committed assets.** Current Google policy is the reason for the explicit gate; see `DATA_GOVERNANCE_AND_LICENSING.md`.

## 7. Roblox structural validation

Future Studio validator should flag:

- unanchored static campus parts;
- imported scripts inside Creator Store assets unless explicitly allowlisted;
- unexpected RemoteEvents/RemoteFunctions in imported assets;
- mesh above platform hard triangle constraints;
- missing `CampusFeatureId` on production world groups;
- missing asset-manifest binding;
- complex collision mode where a simple proxy was expected;
- unnecessary `CanCollide`, `CanTouch`, `CanQuery`, shadows on clutter;
- huge texture usage inconsistent with asset budget;
- duplicated identical meshes/materials instead of reuse;
- excessive `Persistent` streaming models;
- scripts that assume streamed-out objects always exist.

## 8. Performance validation

Test at least:

1. cold join/spawn;
2. fast traversal through vertical slice;
3. stationary view toward dense landmark cluster;
4. rapid turn/camera movement around vegetation;
5. entering/exiting one detailed interior;
6. multiplayer representative load when gameplay exists.

Record:

- FPS/frame-time distribution;
- client memory categories;
- streaming spikes;
- network receive/send where relevant;
- instance counts;
- graphics quality/device class;
- screenshots and profiler captures.

Device gates are defined in `ROBLOX_ARCHITECTURE.md` and should be calibrated against real low-end/normal mobile devices before campus-wide production.

## 9. Visual QA

A useful AI vision workflow is:

1. define approved reference viewpoints with source rights;
2. place Studio camera from corresponding approximate viewpoint;
3. capture in-game screenshot;
4. compare **structure and proportions**, not pixel-perfect color;
5. output discrepancy JSON:
   - silhouette mismatch;
   - missing/extra facade modules;
   - roof shape;
   - window bay spacing;
   - material/color family;
   - vegetation obstruction/context;
   - confidence/reviewer note;
6. human accepts/rejects suggested corrections.

Do not use restricted Google imagery as automated comparison input.

## 10. Building production tracker

Recommended two-layer tracker:

- human/team-facing spreadsheet or project table for status/owners/notes;
- Git-tracked machine-readable export (`building-production.json` or CSV) for validation and agent handoff.

Core columns:

| Field | Meaning |
|---|---|
| feature ID | immutable key |
| name | display name |
| sector | production grouping |
| priority | P0–P3 |
| footprint | missing/approx/verified |
| height | missing/approx/verified |
| reference readiness | blocked/partial/ready |
| imagery rights | open/owned/restricted/uncertain |
| exterior | none/greybox/WIP/verified |
| LOD/collision | status |
| interior tier | none/lobby/major/full |
| QA | status |
| confidence | summary |
| owner | person/agent |
| last reviewed | date |

The spreadsheet is not the geometric source-of-truth; IDs and canonical geometry remain in Git.

## 11. AI agent roles

### CODEX-AUTOMATABLE

- repository/schema work;
- data ingestion and normalization scripts;
- CRS transforms/tests;
- Blender Python generation;
- asset manifest generation;
- Luau/runtime data generation;
- static validation;
- documentation/traceability updates.

### CODEX + ROBLOX MCP

- Studio scene inspection;
- generation of disposable blockouts/props;
- creation of procedural candidates;
- running Studio-side validation/playtests where exposed;
- bulk object-property edits with explicit scope.

### CODEX + BLENDER

- parametric massing;
- road/profile generation;
- modular facade placement;
- export automation;
- collision proxy generation;
- retopology helpers (not blind final-art approval).

### HUMAN DATA COLLECTION

- current facade/landmark photos from authorized public viewpoints;
- physical dimension checks when permitted;
- site verification of entrances/paths/labels;
- confirmation of current building condition.

### HUMAN VISUAL QA

- landmark recognizability;
- art direction consistency;
- AI/model hallucination detection;
- final approval of hero assets and captured references.

### REQUIRES PERMISSION/DATA REQUEST

- institutional plans;
- restricted LiDAR/orthophoto;
- non-public interior access/reference;
- content with unclear reuse rights.

## 12. Current research-package validation

The research branch includes `research/scripts/validate_research.py`, which validates:

- required files;
- JSON/GeoJSON parseability;
- 13 ADR headings;
- 48-requirement traceability entries;
- forbidden bulk/restricted extensions in tracked files;
- obvious Google imagery filenames;
- internal Markdown relative links;
- source-register required fields;
- exact branch ancestry/pins where recorded.

This is a research QA script, not the eventual world validator.
