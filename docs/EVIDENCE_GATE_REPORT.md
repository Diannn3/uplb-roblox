# UPLB Evidence Gate Report

**Decision:** `conditional`

This report is an evidence and rights gate, not a claim that the research AOI is an official UPLB boundary.

## Checks

| Check | Status | Details |
| --- | --- | --- |
| `osm-extract-pinned` | **pass** | expected=9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142 actual=sha256:9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142 |
| `overture-provider-access` | **warning** | blocked; proceed OSM-first without coverage claim |
| `permission-outreach` | **pass** | Templates are drafted locally; no external requests were sent. |
| `dem-license-gate` | **warning** | SRTM/NASA 30 m remains a candidate until endpoint and redistribution terms are recorded. |
| `restricted-source-policy` | **pass** | Google imagery and restricted institutional material remain excluded from ingestion. |

## Current decisions

- OSM is the initial canonical source, pinned by the SHA-256 recorded in the comparison result.
- Overture remains an adapter and comparison source; its current client/catalog and direct-cloud probes are recorded as blocked when unavailable.
- Permission requests are drafts only and must be human-reviewed before sending.
- A legal 30 m DEM remains a terrain baseline candidate; no raster enters canonical data before its rights record is complete.
- Google Street View/Map Tiles and restricted institutional data are excluded from automated ingestion.

## Review posture

A warning or blocked provider does not authorize invented geometry or a coverage claim. Any future source refresh must produce a new hash, source record, and validation report.
