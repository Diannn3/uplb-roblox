# UPLB asset manifests

This directory is the review boundary for third-party and generated assets.

## Two manifest layers

- [`resource-registry.json`](resource-registry.json) is a research and gap registry. It records candidate repositories, libraries, material catalogs, and community signals discovered during the asset audit. A resource is not approved merely because it appears here.
- [`data/canonical/schemas/asset-manifest.schema.json`](../../data/canonical/schemas/asset-manifest.schema.json) is the production manifest contract. Every adopted asset must bind to canonical `uplb:` feature IDs, a source-spec hash, provenance `source:` records, and an explicit verification status.

The original user-provided registry and its license/security guidance remain under [`research/asset-ingest/uplb_asset_ingest`](../../research/asset-ingest/uplb_asset_ingest). The ingest record is [`research/asset-ingest/INGEST_RECORD.json`](../../research/asset-ingest/INGEST_RECORD.json).

## Adoption gate

1. Select a specific file or repository component; do not bulk-vendor a catalog.
2. Confirm the exact license and any attribution/share-alike or platform terms.
3. Record the original URL, author/provider, retrieval date, original hash, and modified hash.
4. Quarantine external files and inspect scripts, nested instances, geometry, textures, scale, collision, and LOD cost.
5. Approve only after visual, legal, and performance review; otherwise keep the candidate as `REFERENCE_ONLY` or `EVALUATE_SELECTIVELY`.

No raw third-party downloads belong in Git. Use ignored local download paths, then commit only approved derivatives and their provenance records.
