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
