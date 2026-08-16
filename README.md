# UPLB in Roblox

A Roblox remake of the University of the Philippines Los Baños (UPLB) campus.

## Project Structure
This project is structured using [Rojo](https://rojo.space/), allowing development to happen in an external code editor (like VS Code) while syncing to Roblox Studio.

* `src/Client/` - Code that runs on the player's device (UI, inputs, local effects). Syncs to `StarterPlayerScripts`.
* `src/Server/` - Code that runs on the Roblox server (data saving, economy, authority). Syncs to `ServerScriptService`.
* `src/Shared/` - Code shared between the client and server (constants, utility functions). Syncs to `ReplicatedStorage`.

## Getting Started
1. Install [Rojo](https://rojo.space/docs/v7/getting-started/installation/).
2. Run `rojo serve` in this directory to start the Rojo server.
3. Open a new place in Roblox Studio.
4. Install the Rojo plugin for Roblox Studio and connect to the server.
5. All code changes in your code editor will now instantly sync into Roblox Studio!

## Architecture Research

The research branch `research/uplb-master-execution-plan` defines the proposed data, GIS, 3D asset, Roblox, MCP, licensing, automation, validation, and phased execution architecture. Start with [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md). No production world-generation system is implemented by that research package.

## Canonical geodata foundation

The production geodata package lives in `tools/geodata/`. Its explicit lifecycle is
`data/raw` (ignored downloads) → `data/candidates` (provider snapshots) →
`data/canonical` (registry-approved campus identities) → generated lightweight
Luau under `src/Shared/Generated/`. OSM identifiers are provenance fields, never
canonical identity; new identities require an explicit promotion/review action.

### Clean-clone workflow

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m tools.geodata.bootstrap --raw tests/fixtures/geodata/osm-small.json --fixture
.\.venv\Scripts\python -m tools.geodata.pipeline --osm tests/fixtures/geodata/osm-small.json --fixture research/fixtures/uplb_reference_points.geojson
.\.venv\Scripts\python -m tools.geodata.ci_checks
```

Full AOI acquisition is deliberately network-opt-in and writes only ignored
replaceable input:

```powershell
python -m tools.geodata.bootstrap --fetch
python -m tools.geodata.pipeline
```

Inspect or explicitly decide provider conflation reviews with:

```powershell
python -m tools.geodata.review list
python -m tools.geodata.review show <review-id>
python -m tools.geodata.review accept <review-id> --reviewed-at 2026-08-17
python -m tools.geodata.promote <candidate-id> --promoted-at 2026-08-17
```

```powershell
python -B -m tools.geodata.pipeline
python -B -m tools.geodata.overture_fallback --python <overture-venv-python>
python -B -m tools.geodata.evidence_gate
python -B -m tools.geodata.phase_gate
python -B -m tools.geodata.overture_check_updates --offline
python -B -m tools.geodata.review list --priority
```

The Overture probe is network-opt-in and bounded. A blocked provider is recorded
as an explicit comparison status; it is not treated as evidence of missing
coverage and does not by itself block the OSM-first greybox POC. Permission
requests under `docs/PERMISSION_REQUEST_TEMPLATES.md` are drafts only. The
authoritative Phase 1 closure report is `data/canonical/phase1-closure-report.json`.
Do not begin terrain, Blender, or persistent Roblox world-generation work while
`worldgenReady` is `false`; the current stop is the explicit human-review gate.
