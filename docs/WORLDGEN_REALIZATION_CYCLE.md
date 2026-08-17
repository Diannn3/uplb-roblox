# World-generation realization cycle

This cycle keeps one deterministic contract between geospatial Python,
Blender, and the later Roblox Studio handoff:

`canonical/context data + selected real NASA DEM`
`→ scene-spec.json`
`→ real Blender verifier`
`→ (after human approval) Roblox Studio MCP verifier`

The checked-in semantic generator and Pillow previews remain useful offline
fixtures. They are not real terrain, Blender geometry, or visual approval.

## Explicit gates

`tools/blender/gates.py` reports independent states for semantic data,
real terrain, Blender availability, mesh generation, rendering, visual review,
and Roblox generation/spatial/playtest. A semantic `pass` cannot promote a
fixture or an unavailable Blender executable to a real-world pass.

## Current stop

The current machine reports Python 3.11, no Blender executable, no installed
`earthaccess`, no Earthdata Login configuration, and no Roblox Studio MCP
connector. The implementation therefore stops before real acquisition and
before any Roblox mutation. Install Python 3.12, configure Earthdata Login
locally, install Blender, then rerun `tools/worldgen/preflight.py`.

No credentials, raw DEM bulk files, `.blend` files, or production Roblox place
changes belong in Git.
