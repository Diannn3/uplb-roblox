# Data Governance and Licensing

_Status: technical licensing research, not legal advice._

## 1. Governance principle

Every retained datum must answer:

1. Where did it come from?
2. When was it accessed/captured?
3. What exact license/permission applies?
4. Can we store it locally?
5. Can we commit it publicly?
6. Can we modify/derive from it?
7. Can we redistribute the derived result?
8. What attribution is required?
9. How confident are we that it describes the current campus?

If any answer is unknown, the record remains `uncertain` and cannot silently enter a redistributable production asset.

`research/sources.json` is the first machine-readable source register.

## 2. Provenance record contract

```json
{
  "id": "source:osm:way:123@2026-08-17",
  "provider": "OpenStreetMap contributors",
  "sourceUrl": "...",
  "accessedAt": "2026-08-17T...Z",
  "capturedAt": null,
  "license": "ODbL-1.0",
  "attribution": "© OpenStreetMap contributors",
  "redistribution": "allowed-with-conditions",
  "derivatives": "allowed-with-conditions",
  "contentHash": "sha256:...",
  "intendedUse": ["building-footprint"],
  "notes": []
}
```

## 3. Legal/technical matrix

| Source | Data | Store? | Modify? | Redistribute? | 3D reconstruction use | Required handling |
|---|---|---:|---:|---:|---|---|
| OpenStreetMap | vectors/tags | Yes | Yes | Yes, conditioned | Yes as data input | ODbL attribution/database obligations; record source |
| Overture Buildings | GeoParquet buildings | Yes | Yes | Yes, conditioned | Yes; docs explicitly include 3D visualization | ODbL + Overture/upstream attribution |
| Overture Transportation | segments/connectors | Yes | Yes | Yes, conditioned | Yes as network input | ODbL + attribution |
| Google Street View Static | imagery | **Do not bulk store** | Restricted | Restricted | **Exclude from automated corpus** | Current policy generally prohibits prefetch/index/store/cache; use only within current terms |
| Google Map Tiles | imagery/tiles | Restricted | Restricted | Restricted | **Exclude from extraction/analysis pipeline** | Current product policy/terms govern non-visual use |
| Mapillary | street imagery | Conditional yes | Conditional | CC/terms dependent | **Review before automated derivative** | current help center says CC-BY-SA; also comply with Terms/Commercial Terms |
| KartaView | street/3D data | Yes under terms | Yes under license | Yes under CC BY-SA conditions | Candidate | attribution/share-alike; keep per-image/source IDs |
| Geoportal Philippines | agency layers | Dataset-specific | Dataset-specific | **Not assumed** | Permission-dependent | obey data owner/download agreement; restricted layers require owner request |
| LiPAD | LiDAR/DEM/orthophoto | Access-specific | Access-specific | **Not assumed** | Permission-dependent | request exact product/coverage; do not commit until terms permit |
| UPLB official photos/maps | institutional content | Reference | Not assumed | Not assumed | Permission-dependent | request permission where required |
| Wikimedia UPLB map | historical map/image | Per file license | Per license | Per license | cross-check only | attribution/share-alike per file page |
| Room TBA app code | code | Yes | Yes | Yes | N/A | MIT notice |
| Room TBA OSM-derived graph | network data | Yes | Yes | ODbL-conditioned | Yes | preserve OSM attribution/ODbL; do not relabel as MIT |
| IMS supplied orientation posters | visual reference | local/private unless permission | Not assumed | **No assumption** | human reference only | do not copy into public repo; geometry remains site-unverified |
| Creator Store assets | Roblox assets | platform/item-specific | item-specific | item-specific | N/A | inspect source/license and scripts; asset manifest required |
| Own photographs | photos | Yes if team owns them | Yes | photographer decides | Yes | capture release/permission and privacy review |

### Google policy gate

Google's current Street View Static policy says content prefetching, indexing, storing or caching is generally prohibited except named exceptions such as panorama IDs. This project therefore has a hard rule: **no Google Street View scraper, downloader, photogrammetry corpus, or retained screenshot archive.** [Google Street View policy](https://developers.google.com/maps/documentation/streetview/policies), accessed 2026-08-17.

## 4. Reference database layout

Recommended feature reference bundle:

```text
references/
  buildings/
    baker-hall/
      index.json
      footprint.geojson
      measurements.json
      source-links.md
      owned-photos/        # only if redistribution permits
      private-reference/   # gitignored if rights do not permit publishing
      photogrammetry/      # generated, normally ignored/LFS
      qa.md
```

`index.json` records every file's source ID, rights status, capture date, hash, and whether an AI agent may ingest it.

## 5. Rights labels

Use machine-readable enums:

- `open-redistributable`
- `open-attribution-required`
- `share-alike`
- `internal-reference-only`
- `permission-required`
- `restricted-do-not-ingest`
- `uncertain`

AI automation must fail closed on `uncertain`, `permission-required`, and `restricted-do-not-ingest` for tasks that create redistributable derivatives.

## 6. Shared `uplb-geodata` evaluation

A shared geodata package/repository is desirable **after** the Roblox proof of concept proves the schema.

Benefits:

- UPPETITE, Room TBA-related workflows, IMS and Roblox can share stable IDs/aliases;
- one provenance record per source instead of duplicated copies;
- corrections propagate to multiple projects;
- easier public contribution/review.

Risks:

- mixing ODbL data with institutionally restricted data;
- accidental relicensing;
- schema changes breaking several apps;
- turning a Roblox experiment into a premature platform project.

Decision: **do not create the shared repository yet.** Keep a clearly separable `data/canonical` design inside `uplb-roblox`; after the vertical slice, extract only the license-compatible, app-neutral subset into a dedicated repository if two or more projects are actually ready to consume it.

## 7. Upstream audit pins

The research source of truth for reproducibility is `research/upstream_repositories.json`:

- `uplb-roblox` base: `66ad829819441447756bd0620e33023e11fc2d5f`
- UPPETITE: `aab2d3dacbe47dd357b27fcbee12a10cbef226a2`
- IMS: `a922d74f881d97075d61ac9277c6927efdabc21e`
- Room TBA current audit: `ff7179c9f7604106720ce587b260ceb7caa9bd4c`
- Room TBA walk graph used by UPPETITE: `feb008212af6b54d3344f44c4a33672b50983fcc`, SHA-256 `b8c57e...27b5e`

## 8. Cost model

### Free/open core

- Git/GitHub for text/data/code;
- Rojo;
- Roblox Studio;
- Blender;
- BlenderGIS;
- OSM;
- Overture;
- Meshroom/AliceVision;
- COLMAP;
- SRTM baseline elevation;
- KartaView/Mapillary according to current terms/API limits.

### Free with access/usage constraints

- OpenTopography APIs may require keys/quotas;
- Copernicus services can have user-category/access changes even when a dataset has a free license;
- LiPAD requires the appropriate request/access path;
- Geoportal downloads are dataset/data-owner dependent;
- Roblox AI generation has product/service limits and should not be assumed unlimited.

### Optional paid

- cloud GPU for photogrammetry if local runs are too slow;
- Git LFS beyond free quota if 3D source grows;
- paid photogrammetry/DCC tools only if open pipeline fails a measured requirement.

### Avoid as architectural dependency

- paid proprietary map imagery requiring restrictive storage terms;
- AI 3D SaaS with unclear redistribution/training rights;
- a large asset subscription before art direction and budgets are proven.

## 9. Permission-request backlog

- Ask UPLB/appropriate unit whether a current campus GIS/building footprint dataset exists and can be reused.
- Ask for any releasable campus planning map/polygon and building directory with coordinates.
- Request LiPAD Los Baños coverage if available; record exact terms before download.
- Ask IMS/building administrators for authorized floor plans or dimensional references before claiming metric indoor accuracy.
- Establish a simple contributor photo release for future student/team reference captures.
