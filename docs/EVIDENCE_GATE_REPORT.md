# UPLB Evidence Gate Report

**Decision:** `pass`

This report is an evidence and rights gate, not a claim that the research AOI is an official UPLB boundary.

## Checks

| Check | Status | Details |
| --- | --- | --- |
| `osm-extract-pinned` | **pass** | expected=9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142 actual=sha256:9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142 |
| `overture-provider-access` | **pass** | blocked explicitly; comparison deferred and no coverage claim is made |
| `permission-outreach` | **pass** | Templates are drafted locally; no external requests were sent. |
| `dem-license-gate` | **pass** | SRTMGL1.003 endpoint, citation, vertical metadata, and redistribution status are recorded. |
| `restricted-source-policy` | **pass** | Google imagery and restricted institutional material remain excluded from ingestion. |

## Source matrix snapshot

| Source | Status | License | Retrieved | Hash | Bounding box | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| `osm` | **validated** | ODbL-1.0 | `2026-08-17` | `sha256:9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142` | `[121.2099966, 14.1290501, 121.2721856, 14.1921433]` | Keep the pinned hash and refresh only through the reproducible harness |
| `overture-buildings` | **blocked-provider-access** | ODbL-1.0 plus upstream attribution | `2026-08-17` | `not recorded` | `[121.2099966, 14.1290501, 121.2721856, 14.1921433]` | Retry a current client/direct-cloud path; do not claim missing coverage |
| `uplb-official-gis` | **permission-request-draft** | Permission not assumed | `None` | `not recorded` | `not recorded` | Human-review and send an access/licensing request |
| `ims-floor-plans` | **permission-request-draft** | Permission not assumed | `None` | `not recorded` | `not recorded` | Request one calibrated Math Building reference set after exterior pilot |
| `mapillary` | **coverage-and-use-unverified** | CC BY-SA/use terms require review | `None` | `not recorded` | `not recorded` | Check coverage without bulk downloading imagery |
| `kartaview` | **coverage-unverified** | CC BY-SA 4.0 per current terms | `None` | `not recorded` | `not recorded` | Verify UPLB coverage and retain per-sequence rights records |
| `geoportal-philippines` | **catalogue-only** | Dataset-specific | `None` | `not recorded` | `not recorded` | Record dataset owner and download agreement before retrieval |
| `lipad` | **permission-request-draft** | Access/product-specific | `None` | `not recorded` | `not recorded` | Request Los Baños coverage and exact redistribution terms |
| `srtm-30m` | **validated-fallback** | NASA Earthdata open data policy; current LP DAAC product openly shared without restriction, with citation requested | `2026-08-17` | `not recorded` | `not recorded` | Retain as the legal baseline; acquire only through the documented Earthdata path when terrain work is approved |
| `copernicus-dem` | **fallback-candidate** | Free-use notice and service terms apply | `None` | `not recorded` | `not recorded` | Compare access and vertical metadata against SRTM |
| `google-imagery` | **excluded** | Restricted platform terms | `None` | `not recorded` | `not recorded` | Do not scrape, bulk-store, or use for automated reconstruction |
| `wikimedia-uplb-map` | **historical-reference-only** | File-specific | `None` | `not recorded` | `not recorded` | Use only as a labelled cross-check, never as current campus boundary |

## Current decisions

- OSM is the initial canonical source, pinned by the SHA-256 recorded in the comparison result.
- Overture remains an adapter and comparison source; its current client/catalog and direct-cloud probes are recorded as blocked when unavailable.
- Permission requests are drafts only and must be human-reviewed before sending.
- SRTMGL1.003 is the rights-resolved 30 m baseline fallback; no raster enters canonical data during this evidence-foundation cycle.
- Google Street View/Map Tiles and restricted institutional data are excluded from automated ingestion.

## Review posture

A warning or blocked provider does not authorize invented geometry or a coverage claim. Any future source refresh must produce a new hash, source record, and validation report.
