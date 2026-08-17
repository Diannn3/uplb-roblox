# World-generation realization cycle

This cycle keeps one deterministic contract between geospatial Python,
Blender, and the later Roblox Studio handoff:

`canonical/context data + selected real NASA DEM`
`→ scene-spec.json`
`→ real Blender verifier`
`→ (after human approval) Roblox Studio MCP verifier`

The checked-in semantic generator and Pillow previews remain useful offline
fixtures. The current cycle also has a validated real-terrain scene, Blender
mesh/renders, and a disposable Roblox Studio MCP bake; the project owner’s
visual approval is recorded and the approved generation, spatial, and short
playtest gates now pass.

## Explicit gates

`tools/blender/gates.py` reports independent states for semantic data,
real terrain, Blender availability, mesh generation, rendering, visual review,
and Roblox generation/spatial/playtest. A semantic `pass` cannot promote a
fixture or an unavailable Blender executable to a real-world pass.

## Current state

Python 3.12, Blender 5.0.0, Earthdata Login, and the Roblox Studio MCP
connector are available locally. The real cycle selected NASADEM_HGT.001,
compiled `98` canonical objects, passed Blender semantic/render QA, and baked
the disposable Edit place with `480` bounded terrain chunks. Production-static
Play mode reuses the baked world without regeneration. The generated spawn is
offset outside the Oblation proxy and samples its own terrain elevation; long-
distance navigation remains deferred. Overture remains blocked and no external
publication or permission request was made.

No credentials, raw DEM bulk files, `.blend` files, or production Roblox place
changes belong in Git.
