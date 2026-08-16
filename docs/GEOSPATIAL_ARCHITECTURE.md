# Geospatial Architecture

## 1. Decision summary

- Interchange CRS: **WGS84 / EPSG:4326**.
- Metric processing CRS: **WGS84 / UTM zone 51N / EPSG:32651**.
- Canonical version-controlled feature representation: **GeoJSON + JSON metadata**, normalized and deterministic.
- Generated working/index formats: GeoPackage/SQLite, GeoParquet, Roblox Luau tables, Blender inputs.
- Local world origin for the proof of concept: UPLB Oblation research fixture (`121.24155 E, 14.16500 N`) until an authorized survey/control point replaces it through an ADR.
- Axis convention: local east → Roblox +X, elevation → +Y, local north → Roblox −Z.
- Project scale proposal: **1 m = 3.5714286 studs** (0.28 m/stud), explicitly configurable and validated visually before production lock.

EPSG identifies 32651 as a metre-based projected CRS with easting/northing axes whose zone covers the Philippines at UPLB's longitude. [EPSG 32651](https://epsg.org/crs_32651/WGS-84-UTM-zone-51N.html), accessed 2026-08-17.

## 2. Why not store only latitude/longitude?

Latitude/longitude is correct for exchange and source provenance, but it is awkward for building dimensions, distances, buffers, offsets, road widths, and Blender operations. UTM gives local metric values while the subsequent local-origin subtraction keeps Roblox/Blender coordinates small and comprehensible.

Coordinate precision and source accuracy are different:

- the mathematical transform can round-trip to sub-millimetre numerical error;
- a source footprint can still be several metres wrong;
- imagery can be outdated;
- a 30 m DEM can be mathematically transformed perfectly while remaining physically too coarse for a curb.

`research/scripts/coordinate_transform.py` tests this distinction explicitly.

## 3. Research AOI

`research/campus_bbox.json` defines:

- west `121.2250`
- south `14.1450`
- east `121.2650`
- north `14.1850`

This is deliberately a **research AOI**, not an official campus boundary. It prevents early clipping while UPLB/authorized campus boundary data is still being investigated.

A smaller vertical-slice AOI is also stored for focused testing.

## 4. Transform contract

Let `(lon, lat)` be WGS84 coordinates.

1. Project to UTM 51N:
   - `(E, N) = project_32651(lon, lat)`
2. Define origin `(E0, N0)` from the project origin feature.
3. Compute local metres:
   - `east_m = E - E0`
   - `north_m = N - N0`
   - `up_m = elevation_m - elevation_origin_m`
4. Convert to Roblox:
   - `X = east_m * STUDS_PER_METER`
   - `Y = up_m * STUDS_PER_METER`
   - `Z = -north_m * STUDS_PER_METER`

Inverse transforms must be available for QA/debugging.

The current fixture origin transforms to approximately:

- UTM easting: `310213.483 m`
- UTM northing: `1566687.470 m`

The supplied test set round-trips below `1e-5 m` numerical error in the current `pyproj` environment.

## 5. Canonical campus feature model

Every physical/semantic feature receives a stable ID independent of display name or geometry source.

Recommended base record:

```json
{
  "id": "uplb:building:baker-hall",
  "featureType": "building",
  "name": "Charles Fuller Baker Memorial Hall",
  "aliases": ["Baker Hall"],
  "geometry": {"type": "Polygon", "coordinates": []},
  "properties": {
    "heightM": null,
    "levels": null,
    "orientationDeg": null,
    "sectorId": "uplb:sector:lower-campus"
  },
  "provenance": ["source-record-id"],
  "confidence": {
    "position": "medium",
    "footprint": "medium",
    "height": "unknown",
    "facade": "unknown"
  },
  "verificationStatus": "needs-site-verification",
  "assetBinding": null
}
```

### Feature types

Minimum planned taxonomy:

- campus / sector
- building / building-part
- floor / space / entrance
- road / walkway / stairs / bridge
- waterway / drainage
- parking / plaza / field
- vegetation-zone / landmark-tree
- sign / lamp / bench / fence / utility-prop
- POI / spawn / interaction-anchor
- navigation-node / navigation-edge

## 6. Stable IDs

IDs must be semantic and immutable:

`uplb:<type>:<slug>`

Examples:

- `uplb:building:baker-hall`
- `uplb:landmark:oblation`
- `uplb:road:loyalty-road`
- `uplb:space:math:mb304`

External IDs are aliases/source bindings, not primary IDs:

```json
"externalIds": {
  "osm": "way/123",
  "overture": "<gers-id>",
  "roomTba": "..."
}
```

This lets upstream geometry change without breaking Roblox references.

## 7. Source layering and conflation

Raw sources remain immutable and separate:

```text
raw/osm/
raw/overture/
raw/uplb-official/
raw/authorized-survey/
raw/room-tba/
```

Normalization produces candidate records; conflation links candidates to a canonical feature. Source priority is **property-specific**, not global:

- identity/name: official UPLB when explicitly authoritative; otherwise locally verified OSM/Room TBA aliases;
- footprint: site survey/authorized plan > locally verified OSM > best validated Overture candidate > placeholder;
- path topology: verified survey > maintained OSM/Room TBA path graph > inferred path;
- facade: owned/authorized current photos > open licensed imagery > human approximation;
- elevation: authorized high-resolution DTM > validated local measurements > 30 m DEM baseline.

No source silently overwrites another. Conflicts generate review records.

## 8. OSM vs Overture comparison protocol

The reproducibility harness under `research/scripts/osm_overture_compare.py`:

1. uses the stored AOI;
2. requests OSM building/highway/waterway features via Overpass;
3. requests Overture `building` features via the official CLI;
4. retains raw downloads only in gitignored `research/raw/`;
5. records SHA-256 hashes;
6. emits counts for buildings, named features, height/floor completeness, paths, and waterways.

The next iteration should add geometry comparison metrics:

- feature count by class;
- percentage of OSM buildings matched to Overture by intersection-over-union;
- median/95th-percentile centroid offset;
- area disagreement;
- named/height/levels completeness;
- representative manually verified landmark table.

Overture itself documents IoU-based building conflation and prioritizes OSM in its building source hierarchy. [Overture Buildings](https://docs.overturemaps.org/guides/buildings/), accessed 2026-08-17.

## 9. Terrain architecture

### Baseline

Use a legal 30 m DEM (SRTM/NASADEM/Copernicus candidate) to establish macro slope and Mount Makiling context. This is not enough for walkways/curbs.

### Refinement layers

- road/path grade constraints from verified paths;
- building-pad flattening based on verified entrances/floor levels;
- creek/waterway carving;
- manually verified retaining walls/stairs;
- authorized LiPAD/NAMRIA higher-resolution data if acquired.

### Terrain pipeline

```text
DEM raster
  -> crop AOI
  -> vertical-datum metadata
  -> resample/project to EPSG:32651
  -> subtract local origin
  -> optional smoothing constrained by roads/building pads
  -> heightfield/mesh preview
  -> Roblox Terrain import/generation test
```

Recommendation: **hybrid Roblox Terrain + localized meshes**. Use Roblox Terrain for large natural ground and forest slope; use meshes/parts for curbs, retaining walls, stairs, bridges, drainage edges, and architecturally controlled hardscape.

## 10. Roads and walkways

Road/path geometry begins as centerlines with attributes:

- stable edge ID;
- type/class;
- width estimate/verified width;
- surface;
- access;
- one-way rules where relevant;
- source/provenance;
- grade/elevation samples;
- confidence.

Generate visual road geometry from centerlines rather than storing only baked meshes. This allows a road width or alignment fix to regenerate output.

Blender is preferred for high-quality swept geometry and terrain conforming; a simpler Roblox/Luau generator can produce greybox splines/segments for fast QA.

## 11. Vegetation

Do not attempt a false tree-by-tree twin without data. Use three levels:

1. **landmark trees** — individually identified and manually placed/verified;
2. **structured plantings** — approximate rows/zones from visible evidence;
3. **biome scatter** — seeded procedural placement based on land-cover/zone polygons.

Store the seed and generation parameters so the forest does not randomly change between builds.

## 12. Indoor coordinate bridge

IMS demonstrates why indoor spaces and route topology must remain separate. For a future detailed building:

- building footprint/orientation/entrances are tied to campus coordinates;
- each floor has its own local 2D/3D coordinate frame;
- floor geometry is transformed by a building placement matrix into world coordinates;
- route graph nodes bind to door/stair/entrance feature IDs.

The current IMS poster-derived coordinates are useful semantically but remain `needs-site-verification` and must not be scaled to metres without calibration.

## 13. Generated formats

Canonical source-controlled data:

- GeoJSON for spatial features;
- JSON for metadata, provenance, assets, validation and configuration.

Generated/derived:

- GeoPackage or SQLite spatial index for analyst convenience;
- GeoParquet for bulk analytics when useful;
- normalized Blender import JSON/GeoJSON;
- generated Luau modules for runtime lookup;
- generated Studio world chunks/blockouts.

Generated files contain a source hash/version and must never become a second manually edited truth.
