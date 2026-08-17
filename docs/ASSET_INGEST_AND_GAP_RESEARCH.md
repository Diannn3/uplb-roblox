# UPLB asset ingest and gap research

**Audit date:** 2026-08-17

**Scope:** user-provided asset ingest bundle plus a targeted search of official Roblox documentation, GitHub, asset-library license pages, and Roblox developer community discussions.

## Outcome

The supplied archive was ingested as research evidence. It contains 15 curated resource records, license/security guidance, integration priorities, templates, and inert fetch scripts; it contains no binary third-party assets. The archive and extracted registry are hash-recorded in [`research/asset-ingest/INGEST_RECORD.json`](../research/asset-ingest/INGEST_RECORD.json).

The gap audit found a missing reproducible Roblox toolchain layer and a few useful, selectively licensed asset sources. It did **not** justify bulk downloads, a new runtime dependency, or replacing the existing deterministic Blender/geodata pipeline. Candidate status and next actions are machine-readable in [`assets/manifests/resource-registry.json`](../assets/manifests/resource-registry.json).

## Existing bundle coverage

The bundle already covers the high-value first-pass asset families:

- modular building and facade references: BasicProceduralBuilding, Downtown City MegaKit, Kenney Building Kit;
- roads and street furniture: Kenney City Kit Roads;
- context vegetation: Quaternius Ultimate Nature and Stylized Nature;
- PBR/HDRI/material sources: Poly Haven;
- procedural/reference research: BCGA, BuildingNodes, modular_tree, Blosm;
- future Roblox tooling: Lune, luau-roblox, BloxForge;
- a Creator Store quarantine policy.

The supplied policy is retained unchanged: CC0 or clearly permissive sources are preferred, exact hashes and provenance are required, Creator Store scripts are quarantined, and Google-derived imagery/3D is excluded.

## Verified gaps and recommendations

| Gap | Candidate | Evidence | Decision |
|---|---|---|---|
| Reproducible Roblox CLI tools | [Rokit](https://github.com/rojo-rbx/rokit), [Rojo](https://github.com/rojo-rbx/rojo), [Selene](https://github.com/Kampfkarren/selene), [StyLua](https://github.com/JohnnyMorganz/StyLua) | Their repositories document the toolchain manager, filesystem/Git sync, Luau linting, and deterministic formatting. Roblox's [external-tools guidance](https://create.roblox.com/docs/projects/external-tools) also documents Rojo/Wally-style workflows. | Adopt after review, pinned locally. Do not install during this ingest cycle. |
| Package management without accidental dependencies | [Wally](https://github.com/UpliftGames/wally) | Official repository documents lockfile-based package resolution. | Evaluate only when a real shared Luau dependency exists; no packages for the first terrain slice. |
| Headless Roblox model/place validation | [rbx-dom](https://github.com/rojo-rbx/rbx-dom), plus the bundled [Lune](https://github.com/lune-org/lune) | rbx-dom provides Rust DOM/serialization utilities; Lune provides a standalone Luau runtime and Roblox serialization helpers. | Future adapter. Studio MCP and Rojo remain the current path. |
| Additional low-poly tropical context | [Quaternius 150+ Low Poly Nature Models](https://quaternius.itch.io/150-lowpoly-nature-models) | Pack page identifies the pack as CC0. | Evaluate individual files only; hash and record each adopted file. |
| Material coverage for concrete, paving, soil, grass, and metal | [ambientCG](https://ambientcg.com/) and its [license page](https://docs.ambientcg.com/license/) | ambientCG states that downloadable assets are CC0 1.0 and may be included in games. | Evaluate named materials selectively; resize/pack for Roblox and preserve URL/hash even when attribution is optional. |
| GIS/DEM import comparison | [BlenderGIS](https://github.com/domlysz/BlenderGIS) | Useful OSM/GeoTIFF/DEM import reference; repository is GPL-3.0. | Reference only. Keep project-owned deterministic Blender scripts as source of truth and do not add a GPL interactive dependency. |
| Supplemental free vegetation | [OpenGameArt low-poly nature group](https://opengameart.org/content/low-poly-nature-group) | Community page advertises a CC0 group, but the license/author record must be checked per file. | Conditional evaluation only; reject ambiguous files. |

Rokit is the preferred tool-manager candidate for a new project because its official repository documents compatibility with existing Foreman/Aftman projects and a local install workflow. The project should still pin and review all tool versions before adopting it; this report does not authorize installation.

## Community research signal

Recent [Roblox developer discussion](https://www.reddit.com/r/robloxgamedev/comments/1u0ch0k/any_tips_for_building/) and a second [Blender/building discussion](https://www.reddit.com/r/robloxgamedev/comments/1ksnmvo) broadly reinforce a greybox-first workflow: establish scale and layout, use Blender for serious mesh production, and keep Roblox Studio responsible for scripts, physics, and presentation. A separate [plant-pack discussion](https://www.reddit.com/r/robloxgamedev/comments/1em3w99/) reinforces style/overdraw consistency. These are non-authoritative workflow signals only; Reddit is not used to establish licensing, UPLB facts, or dimensions.

## Deliberately not adopted

- No bundle fetch script was executed, and no GitHub repository or asset archive was cloned.
- No Creator Store model is approved. Any future import remains quarantined and script-inspected.
- The [roblox-procedural-worlds repository](https://github.com/Gzeu/roblox-procedural-worlds) is a reference lead only until its license and current data model are inspected.
- BlenderGIS, Blosm, BCGA, BuildingNodes, and modular_tree remain research/reference candidates where license, Blender-version, or interactive-state risk is material.
- No new DEM is silently substituted. The existing pinned 30 m baseline and its evidence gate remain authoritative until a source decision changes.

## Recommended next implementation order

1. Review and accept the registry/report as the asset evidence gate.
2. Add a small, project-local Rokit/Rojo/Selene/StyLua trial on a new branch; run only lint/format/sync checks.
3. Select one ambientCG material and one Quaternius vegetation asset for a disposable quarantine import; record original/modified hashes and budget measurements.
4. Build the UPLB-specific facade, bench/lamp, covered-walk, and vegetation modules procedurally or from the approved candidates.
5. Bind only accepted derivatives to `asset:` manifests and the Oblation/Freedom Park/Baker Hall vertical-slice feature IDs.

No external permission request or publication is part of this audit. Any source that requires permission remains a draft template or a `verified-conditional` candidate until a human approval is recorded.
