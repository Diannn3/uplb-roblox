# UPLB Evidence Gate Report

**Decision:** `pass`

This report is an evidence and rights gate, not a claim that the research AOI is an official UPLB boundary.

## Checks

| Check | Status | Details |
| --- | --- | --- |
| `osm-extract-pinned` | **pass** | expected=9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142 actual=sha256:9f766739c1ad0088170c708d222c246b47b4dc684120f1f57f252d6f290f6142 |
| `overture-provider-access` | **pass** | blocked explicitly; comparison deferred and no coverage claim is made |
| `permission-outreach` | **pass** | Templates are drafted locally; no external requests were sent. |
| `dem-acquisition` | **pass** | NASADEM_HGT.001 acquired and compared; selected NASADEM_HGT.001; archive, payload, processed, retrieval, and local coverage metadata are recorded. |
| `dem-license-gate` | **pass** | SRTMGL1.003 and NASADEM_HGT.001 rights, endpoint, citation, vertical metadata, and redistribution status are recorded. |
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
| `srtm-30m` | **validated-comparison-input** | NASA Earthdata open data policy; current LP DAAC product openly shared without restriction, with citation requested | `2026-08-17` | `archive=sha256:3169d32283271c39307371ee01a6cbb66c32143e4f1e1c55c152f44809dd2d81; payload=sha256:f4761f7b97ef7e78dff39e9f8b3a649ebddce19479bbd316a6f018d85305260c; processed=sha256:c7eae8e38b5bfbd92873a1c8c86cbddee38b058e64db26648b805cd994aa011d` | `[121.2099966, 14.1290501, 121.2721856, 14.1921433]` | Retain as a measured comparison input; NASADEM_HGT.001 is selected for the controlled slice |
| `nasadem-30m` | **validated-selected-baseline** | NASA Earthdata open data policy; public-domain/open reuse with citation requested | `2026-08-17` | `archive=sha256:c115ac7027d4c6160b308ac280b5e259309680ed6347475407cb071194a42398; payload=sha256:730d5350ef7663eb7ae00f9cbe861549156540a055dc75d6efaa4f0d19a7fbe9; processed=sha256:3e6dcd85e480cbfaaea342bc18a8d48290af4adff0e7af55bcb72e7144438e84` | `[121.2099966, 14.1290501, 121.2721856, 14.1921433]` | Use as the controlled-slice baseline; obtain higher-resolution authorized terrain before campus-wide production |
| `copernicus-dem` | **fallback-candidate** | Free-use notice and service terms apply | `None` | `not recorded` | `not recorded` | Compare access and vertical metadata against SRTM |
| `google-imagery` | **excluded** | Restricted platform terms | `None` | `not recorded` | `not recorded` | Do not scrape, bulk-store, or use for automated reconstruction |
| `wikimedia-uplb-map` | **historical-reference-only** | File-specific | `None` | `not recorded` | `not recorded` | Use only as a labelled cross-check, never as current campus boundary |

## Current decisions

- OSM is the initial canonical source, pinned by the SHA-256 recorded in the comparison result.
- Overture remains an adapter and comparison source; its current client/catalog and direct-cloud probes are recorded as blocked when unavailable.
- Permission requests are drafts only and must be human-reviewed before sending.
- NASADEM_HGT.001 is the selected rights-recorded 30 m baseline for the controlled slice; the comparison and processed hashes are recorded in the terrain measurement below.
- Google Street View/Map Tiles and restricted institutional data are excluded from automated ingestion.

## DEM acquisition snapshot

- Status: `ready-real-terrain`; comparison: `validated-raster`; products: `SRTMGL1.003, NASADEM_HGT.001`.
- Selected baseline: `NASADEM_HGT.001`; granule: `NASADEM_HGT_n14e121`; retrieved: `2026-08-17T04:39:12.238467+00:00`.
- Archive SHA-256: `sha256:c115ac7027d4c6160b308ac280b5e259309680ed6347475407cb071194a42398`; HGT payload SHA-256: `sha256:730d5350ef7663eb7ae00f9cbe861549156540a055dc75d6efaa4f0d19a7fbe9`; processed heightfield SHA-256: `sha256:3e6dcd85e480cbfaaea342bc18a8d48290af4adff0e7af55bcb72e7144438e84`.
- Local coverage: `{'eastM': 612.6689003391075, 'northM': 189.0923085224349, 'southM': -950.9076914775651, 'westM': -1517.3310996608925}`; revision: `terrain-v0.2-real`.

## Review posture

A warning or blocked provider does not authorize invented geometry or a coverage claim. Any future source refresh must produce a new hash, source record, and validation report.
