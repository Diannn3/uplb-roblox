# Terrain and greybox POC gate

## Current stop

The Phase 1 evidence gate is `PASS_FOR_POC` and `worldgenReady=true`. The
separate greybox branch currently stops at the visual review gate because this
machine has no `blender`/`blender.exe` on PATH and no Earthdata raster or
credentials are available. The generated artifacts are therefore explicitly
labelled `synthetic-fixture` and `conditional-blender-unavailable`; they are
not a NASA DEM comparison, a Blender mesh validation, or final visual approval.

## Terrain sources

- [SRTMGL1.003 landing page](https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003)
- [NASADEM_HGT.001 DOI landing page](https://doi.org/10.5067/MEASURES/NASADEM/NASADEM_HGT.001)
- [NASADEM user guide](https://lpdaac.usgs.gov/documents/1318/NASADEM_User_Guide_V12.pdf)

Both products are recorded at 30 m, EPSG:4326/WGS84 horizontally, and EGM96
metres vertically. Acquisition is fail-closed through current Earthdata
Search/Earthdata Cloud routes; the retired LP DAAC Data Pool is not used.

`tools/terrain/acquire.py` derives the query bounding box from the frozen
vertical-slice AOI, validates product/version and granule overlap, then records
retrieval metadata and hashes under ignored `data/raw/terrain/`. The lightweight
`tools/terrain/hgt.py` reader preserves big-endian EGM96 values without GDAL.
Both real products are run through the same local EPSG:32651 sampling path
before `tools/terrain/compare.py` chooses a baseline from measured evidence.

`config/terrain.json` intentionally has `baseline: null`. A synthetic fixture
must not select a NASA baseline. A credentialed acquisition can run:

```powershell
python -m tools.terrain.acquire srtm
python -m tools.terrain.acquire nasadem
```

For deterministic pipeline tests only:

```powershell
python -m tools.terrain.acquire srtm --fixture
python -m tools.terrain.acquire nasadem --fixture
python -m tools.terrain.generate_outputs
```

## Greybox generator

Blender's official [5.0 command-line manual](https://docs.blender.org/manual/en/5.0/advanced/command_line/arguments.html)
documents `--background` and `--python`. The intended invocation is:

```powershell
blender.exe --background --python tools/blender/generate_greybox.py -- --slice data/vertical-slices/v0.1 --output data/generated/greybox-v0.1
```

Until Blender is installed, the Python semantic fallback produces a traceable
world manifest, structural QA, fixed-camera semantic previews, and a
determinism record. It does not create a `.blend` file or pass the human visual
gate. Its explicit execution states are in
`data/generated/greybox-v0.1/execution-gates.json`; semantic determinism is not
equivalent to real terrain, Blender mesh, render, or visual approval. Review
those paths only as a dry run.

The authoritative generated-world input for both consumers is
`data/generated/worldgen-v0.1/scene-spec.json`. The real Blender command is:

```powershell
blender.exe --background --python-exit-code 10 --python tools/blender/build_scene.py -- --scene-spec data/generated/worldgen-v0.1/scene-spec.json --output data/generated/blender-v0.1
```

Do not start Roblox Studio/MCP handoff until the actual Blender mesh and render
gates pass and the project owner explicitly approves all six real renders.
