# Prompt for Codex: ingest this bundle

You have been given the UPLB Asset Ingest bundle.

Read:
- ASSET_REGISTRY.json
- LICENSE_MATRIX.csv
- UPLB_ASSET_ARCHITECTURE.md
- INTEGRATION_PRIORITY.md
- SECURITY_AND_LICENSE_RULES.md

Do not install or vendor everything automatically.

Tasks:
1. Audit the project repo's current asset/worldgen architecture.
2. Create an `assets/manifests/` schema compatible with ASSET_REGISTRY.json.
3. Add provenance fields: source URL, license, original hash, modified hash, author/provider, import date, category, triangle count, texture set, collision policy, approved use.
4. Keep research-only/GPL tools separate from shipped Roblox assets.
5. Prioritize CC0 asset packs for reusable environment/context pieces.
6. Do not download huge libraries wholesale. Select assets based on a stated UPLB need.
7. Build an initial UPLB Architecture Kit specification covering windows, doors, columns, sunshades, roof edges, railings, stairs, covered walkways, benches, lamps, signs, road/curb modules, and vegetation pools.
8. For every proposed third-party asset, classify: USE AS-IS / MODIFY / PROCEDURAL REFERENCE / CUSTOM MODEL / REJECT.
9. Do not pull any Google-derived imagery/3D city data.
10. Do not add unreviewed third-party scripts from Roblox models.
11. Preserve deterministic generation and scene-spec-as-source-of-truth.
12. Output a plan first unless explicitly instructed to execute.

The goal is to reduce manual modeling without sacrificing UPLB identity, reproducibility, or license hygiene.
