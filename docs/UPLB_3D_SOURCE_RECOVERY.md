# UPLB 3D Source Recovery Playbook

## Purpose

Recover existing UPLB 3D/CAD/reference material before duplicating modeling work.
A recovered source is evidence, not automatically a shippable Roblox asset.

## Highest-value lead: 2014 UPLB virtual campus

The ISCE 2014 paper *Design, Implementation, and Evaluation of a 3D Virtual
Classroom Environment in a Computer Cluster* states that UPLB virtual building
models were patterned from architectural blueprints and built using Google
SketchUp and Blender. Figures identify Baker Hall, Biological Sciences, CAS
Annexes 1/2, Main Library, Physical Sciences, CEAT, CEM, CDC, DL Umali, Student
Union, Mariang Banga, Oblation Park, Freedom Park, and the UPLB Gate.

Evidence:
- https://id.scribd.com/document/990184030/ISCE2014-Proceedings-FINAL3
- https://lbtimes.ph/cinterlabs-showcases-3d-avatar-based-virtual-environment-program/

### Recovery order

1. UPLB Institute of Computer Science / historical CINTERLABS archives.
2. Project authors / advisers, asking specifically for old `.skp`, `.blend`, `.dae`, `.obj`, texture folders, and documentation.
3. University Library / institutional digital archives / old project servers or backups.
4. Only after source recovery fails, reconstruct the building ourselves.

### Questions to record for every recovered file

- Who owns the file and underlying design?
- Is derivative/republication use permitted?
- What building revision/date does it represent?
- Was it based on an architectural blueprint, field measurement, or visual approximation?
- What units, coordinate system, and origin were used?
- Are textures original, third-party, or from an old warehouse/library?
- Does the asset contain interiors that should not be published?

Do not import a recovered file into the production asset library until these are
recorded in an asset manifest.

## Existing scan leads

### UPLB Oblation

- https://sketchfab.com/3d-models/uplb-oblation-cba18bfbafdf49779e484f767dc9fe5d
- roughly 797.8k triangles / 405k vertices at the time of research.
- page description states DJI O3 Air Unit capture.

### UPLB Physical Sciences Building

- https://sketchfab.com/3d-models/uplb-physical-sciences-building-5c154f0033dd4ff3b13a5aab1ebfbe50
- roughly 1M triangles / 504.9k vertices at the time of research.

Treat both as **permission-required** until a reusable license is explicitly
confirmed. If permission is granted, keep the raw scan as a high-poly reference
or master input; generate optimized derivatives for Roblox.

## Institutional GIS/LiDAR leads

UPLB Phil-LiDAR 1 work explicitly processed building footprints from LiDAR data
for Laguna/MIMAROPA:

https://www.ukdr.uplb.edu.ph/journal-articles/1657/

Ask the relevant UPLB geospatial/ERSG/Phil-LiDAR data custodians whether any
campus-covering point cloud, DSM/DTM, or derived building layer can be used.
Do not assume publication of a paper grants access to the underlying dataset.

## Structural/building-study leads

Useful factual constraints exist in UPLB civil-engineering studies, including:

- Main Library: four-storey reinforced-concrete building, constructed in 1970:
  https://www.ukdr.uplb.edu.ph/etd-undergrad/5515/
- University Health Services Main Building: approximately 8 m, two storeys,
  reinforced concrete, constructed in 1971:
  https://www.ukdr.uplb.edu.ph/etd-undergrad/5523/
- Campus seismic-audit work references a broader inventory of UPLB buildings:
  https://www.ukdr.uplb.edu.ph/professorial_lectures/436/

Use only facts actually disclosed by the available source unless full documents
are lawfully accessible.

## Licensed photographic evidence

Example Baker Hall reference:

https://commons.wikimedia.org/wiki/File:University_of_the_Philippines_(UPLB)_-_Baker_Hall_(Los_Baños,_Laguna;_2017-02-16).jpg

The file page specifies CC BY-SA 4.0. Preserve author/license provenance and
review derivative/share-alike implications before using imagery for texture
baking or photogrammetric derivatives.

## Our own capture fallback

When no source asset is recoverable:

1. Build a capture plan for the building.
2. Obtain any needed site/flight permissions.
3. Capture overlapping exterior imagery with scale references.
4. Reconstruct using RealityScan or COLMAP.
5. Align the reconstruction to canonical footprint/measurements.
6. Retopologize; never ship the dense scan directly.
7. Generate LODs and simple collision.
8. Validate against the reference pack.

COLMAP 4.x supports SfM, dense MVS, Poisson/Delaunay meshing, QEM mesh
simplification, and texture mapping, making it suitable as the reproducible open
capture path: https://github.com/colmap/colmap

## Recovery gate

A building moves from `source-recovery` to `reference-ready` only when its
reference pack has:

- canonical or explicitly proposed FeatureId,
- current footprint evidence,
- height/floor evidence or an explicit placeholder policy,
- all reusable-source rights states recorded,
- enough facade/roof coverage to choose a modeling strategy,
- an explicit decision on recovered source / scan / photogrammetry / procedural / custom.
