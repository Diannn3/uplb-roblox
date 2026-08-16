# Roblox Architecture

## 1. World topology

### Recommended initial topology

**One outdoor campus place with `Workspace.StreamingEnabled`, plus optional separate heavy interior places later.**

Reasons:

- campus continuity and navigation benefit from one coherent outdoor world;
- streaming is designed to load/unload Workspace content by relevance and Roblox recommends it for large worlds;
- multiple places introduce teleport/join boundaries and complicate seamless campus traversal;
- separate places remain useful when an interior becomes independently heavy or needs different deployment/game rules.

Roblox documents that instance streaming improves join time and memory efficiency and can improve performance. [Streaming](https://create.roblox.com/docs/workspace/streaming), accessed 2026-08-17.

### Split triggers

Reconsider multiple places only when measured data shows one of:

- a detailed interior cannot meet mobile memory/performance targets even with streaming;
- independent teams/releases require isolation;
- gameplay intentionally treats an interior as a separate session;
- world-content management becomes materially safer with a split.

## 2. Source ownership matrix

| Content | Authoritative source | Editor | Persistence |
|---|---|---|---|
| Luau | Git | Codex/editor | Rojo sync |
| canonical geodata | Git JSON/GeoJSON | scripts/GIS/editor | generated imports |
| provenance/licenses | Git | human/agent | manifests |
| Blender source | Git LFS later | Blender/Codex scripts | `.blend` source |
| exported meshes | generated cache / selective LFS | Blender pipeline | upload + asset manifest |
| Roblox uploaded asset IDs | Git manifest | upload workflow | Roblox asset cloud |
| generated blockout | Git spec is truth | tool/MCP | regenerate in Studio |
| hand-authored Terrain/scene composition | designated Studio source place snapshot | Studio | future Git LFS/controlled snapshot |
| MCP-generated persistent object | **never MCP alone** | MCP/Studio | either regenerate from Git spec or capture in authored scene + manifest |

The core rule: **every persistent object has exactly one authority.** Studio is not allowed to silently become the only copy of something we expect to reproduce.

## 3. Rojo/Luau layout proposal

Do not implement yet; target structure:

```text
src/
  Client/
    Controllers/
    UI/
    Rendering/
    MainClient.client.lua
  Server/
    Services/
    Systems/
    MainServer.server.lua
  Shared/
    Domain/
    Config/
    Geo/
    Networking/
    Types/
  Generated/
    CampusData.lua        # generated, never hand-edited
    AssetManifest.lua     # generated subset for runtime
```

Potential non-runtime tooling:

```text
tools/
  geodata/
  worldgen/
  blender/
  validation/
```

Generated Luau should include a generator version and canonical-data hash.

## 4. Package/toolchain policy

Keep the runtime lean.

Recommended foundation when implementation begins:

- Rojo for filesystem↔Studio code/data mapping;
- StyLua for formatting;
- Selene (or current equivalent) for static linting if compatible with current Luau workflow;
- explicit Luau types;
- a small test runner only where it adds value to pure modules;
- CI that validates JSON/GeoJSON, generated-file freshness, lint/format and source manifests.

Do not add a heavyweight service/controller framework simply because it is popular. Native Roblox services plus small typed modules are enough until a measured complexity need appears.

## 5. Domain separation

### Shared domain

Pure definitions:

- feature IDs/types;
- coordinate transforms (or generated transform constants);
- campus metadata access;
- asset bindings;
- interaction contracts;
- route graph types.

### Server

Authority for:

- persistent player state;
- economy/progression if added;
- authoritative interactions that affect other players/world state;
- validated transport/gameplay systems.

### Client

Owns:

- map/navigation UI;
- local visual effects;
- camera/input;
- streaming-aware presentation;
- non-authoritative interaction hints.

## 6. CollectionService / tags

Static world objects should bind to stable feature IDs using attributes/tags rather than bespoke scripts on every model.

Example model attributes:

- `CampusFeatureId = "uplb:building:baker-hall"`
- `AssetManifestId = "asset:baker-hall:v3"`
- `SourceRevision = "canonical:..."`
- `VerificationStatus = "verified-exterior-medium"`

Tags can group behaviors:

- `CampusBuilding`
- `NavigableEntrance`
- `InteractiveLandmark`
- `StreamingHero`

Avoid putting scripts inside hundreds of imported free models.

## 7. Studio MCP workflow

Roblox Studio MCP currently exposes script operations plus content-generation tools. [MCP docs](https://create.roblox.com/docs/studio/mcp), accessed 2026-08-17.

Recommended loop:

```text
Git spec/data
  -> Codex reasoning/scripts
  -> Studio MCP execution
  -> Studio result
  -> automated inspection/playtest where possible
  -> human visual QA
  -> either (A) discard/regenerate, or (B) record accepted asset/state in source system
```

### MCP ownership rules

1. MCP may edit Rojo-owned scripts only when the same changes are reflected back in the Git working tree; prefer editing local files directly for Rojo-owned code.
2. MCP may generate **ephemeral** blockouts freely inside a dedicated `GeneratedDrafts` container.
3. A generated object cannot become production merely by being moved in Explorer.
4. Promotion requires an asset/spec manifest and source decision.
5. If a procedural model is intended to be deterministic, store its generator/spec parameters in Git.
6. If a Studio-authored unique object is accepted, it must be captured in the designated Studio source snapshot and asset manifest before deletion/regeneration is possible.
7. Never let MCP overwrite canonical geodata.

## 8. Studio source snapshot strategy

Terrain and certain editor-authored spatial state cannot be responsibly left only in the Roblox cloud.

After the vertical slice, implement one of these controlled strategies:

**Preferred:** a designated source `.rbxlx`/place snapshot under Git LFS, with Rojo code excluded/overlaid during development. Snapshot updates are intentional checkpoints, not every keystroke.

Alternative: a chunked set of `.rbxmx`/model source files under LFS if terrain/world partitioning proves maintainable.

Current `.gitignore` continues to exclude Roblox place/model formats during research; implementation must change it only after ADR-011 is approved and Git LFS is configured.

## 9. Streaming architecture

`StreamingEnabled` is a baseline requirement for the outdoor campus.

Design rules:

- world models grouped by meaningful regions/buildings;
- avoid making large areas `Persistent` unless a system truly requires it;
- client scripts must tolerate streamed-out instances;
- never assume a distant landmark object exists locally;
- use canonical data for map/UI state rather than inspecting streamed Workspace to discover the campus;
- keep essential shared definitions in ReplicatedStorage, not duplicated on every streamed model.

## 10. Device acceptance targets

These are **project targets, not Roblox platform guarantees**.

### Low-end mobile

- functional play at 30 FPS target in the vertical slice under representative load;
- no crashes/memory-pressure failure during a complete traversal;
- aggressive streaming/LOD;
- mostly 256–512 textures;
- no unnecessary real-time shadows on clutter;
- foliage and transparent overdraw controlled.

### Normal mobile

- 30–45+ FPS target during traversal;
- medium visual distance;
- hero landmarks retain recognizable silhouette/materials.

### PC

- 60 FPS target on a representative mid-range machine where practical;
- higher render fidelity/streaming distances without separate asset set unless profiling proves necessary.

Performance is validated with Studio/client profiling, not guessed from triangle totals alone.

## 11. Per-asset and scene budgets

Hard platform mesh rule: individual custom meshes ≤20,000 triangles. [Roblox specifications](https://create.roblox.com/docs/art/modeling/specifications), accessed 2026-08-17.

Internal budgets are defined in `ASSET_PIPELINE.md`. For scene-level budgets, use measurement gates:

- render CPU/GPU frame time;
- memory categories;
- streamed instance count;
- visible triangles/draw-call proxies where tooling exposes them;
- texture memory;
- network/replication spikes during movement.

Do not hard-code a global “million triangles = safe” myth without profiling target devices.

## 12. World-generation boundary

The campus greybox generator should create only replaceable derived content:

- terrain preview;
- road/path meshes;
- extruded building masses;
- feature markers/labels;
- validation markers.

It must not become a giant monolithic script that owns final hand-authored landmarks. Generated and authored layers coexist with clear collection names and IDs.

## 13. Interactions/gameplay hooks

Keep reconstruction independent from gameplay. A building can exist without a quest script.

Gameplay uses feature IDs to attach behavior:

```text
canonical feature ID -> interaction registry -> runtime behavior
```

This permits future campus tours, orientation, events, social spaces, navigation, jeepney transport, or quests without corrupting the spatial model.
