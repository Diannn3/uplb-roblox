# UPLB Asset Ingest Bundle

This bundle turns the researched repositories and asset libraries into a Codex-ready registry.

## Important

This ZIP intentionally does **not** contain hundreds of megabytes/gigabytes of third-party asset packs. Instead it contains:
- the complete curated resource registry,
- license/use classifications,
- integration priorities,
- UPLB asset architecture,
- per-resource notes,
- asset manifest schema/templates,
- fetch scripts for open GitHub repos,
- a Codex ingest prompt.

Large CC0 libraries (Kenney, Quaternius, Poly Haven) should be downloaded **selectively** based on concrete UPLB asset needs. This keeps the project small, auditable, and reproducible.

## Start here

1. Read `INTEGRATION_PRIORITY.md`.
2. Read `SECURITY_AND_LICENSE_RULES.md`.
3. Give `CODEX_INGEST_PROMPT.md` to Codex when you're ready.
4. If you want local source snapshots of the clearly licensed GitHub repos, run:
   - Windows: `fetch/fetch_open_source_repos.ps1`
   - macOS/Linux: `fetch/fetch_open_source_repos.sh`
5. Register every adopted asset using `templates/asset-record.example.json`.

## Core rule

Third-party libraries are inputs and references. The final project should evolve toward a UPLB-specific architecture/environment kit with clear provenance and deterministic generation.
