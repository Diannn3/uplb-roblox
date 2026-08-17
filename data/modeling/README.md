# UPLB Modeling Production Data

This directory is the Git-side control plane for campus-scale 3D production.
It does **not** make Blender or Roblox Studio canonical.

## Files

- `model-source-registry.json` — evidence and recovery leads for models, scans, plans, LiDAR, photographs, and reconstruction tools.
- `building-production-registry.json` — per-building strategy, priority, status, source links, and canonical/proposed feature binding.
- `architecture-kit-v0.1.json` — reusable UPLB module families, material classes, dimensions, and triangle budgets.
- `building-specs/` — production specifications for individual buildings. Baker Hall is the first prototype.
- `reference/` — pinned read-only snapshots used to reproduce prototypes; these are never substitutes for canonical data.
- `source-recovery-queue.json` — generated action queue.
- `production-foundation-report.json` — generated validation/status report.

Run:

```powershell
python -m tools.modeling.pipeline --check --generate-prototypes --write-report
```

Generated OBJ prototypes are intentionally crude. They validate scale, identifiers,
source binding, and asset handoff before detailed modeling begins.

## Production wave 01 — Baker + central academic buildings

The first content-production wave is evidence-aware and intentionally separates
canonical identity from proposed production handles.

Generate Baker Hall first, followed by the central-wave prototypes:

```powershell
python -m tools.modeling.pipeline `
  --check `
  --generate-prototypes `
  --generate-baker-production `
  --generate-central-wave `
  --write-report
```

Outputs:

- `assets/generated/production/baker-hall/` — Baker v0.2 reference-derived exterior + QA/report.
- `assets/generated/production/central-wave/` — DL Umali, Student Union, Physical Sciences,
  ULKC/Main Library candidate massing, CAS Annex 2, and Dean Edelwina C. Legaspi Hall.
- `assets/generated/production/central-wave/manifest.json` — hashes, candidate identity status,
  QA, triangle counts, height/facade confidence, and roof policy.
- `data/modeling/next-wave-source-gaps.json` — explicit blockers for Oblation, IBS, CEM, CEAT,
  CAS Annex 1, CDC, and the UPLB Gate.

Important constraints:

- Candidate OSM IDs remain source evidence. A generated `uplb:*` production handle is **not**
  a canonical promotion.
- `longest-edge-proxy` is deterministic only; it is not a claim that the selected edge is the
  surveyed main entrance facade.
- Known roof tags may be recorded while exact roof geometry remains deferred.
- No third-party reference photographs are vendored by this layer.
- ULKC/Main Library remains massing-only because the current candidate is tagged construction
  and legacy Main Library evidence must not be silently transferred to a potentially different
  building state.
