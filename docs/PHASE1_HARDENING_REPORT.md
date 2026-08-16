# Phase 1 Geospatial Hardening Report

**Decision:** `conditional`

A `pass` is required before terrain, Blender, or Roblox world-generation work. A `conditional` result records known evidence/provider or rights blockers and intentionally stops the project at the Phase 1 gate.

## Checks

| Check | Status | Details |
| --- | --- | --- |
| `candidate-canonical-separation` | **pass** | canonical feature IDs are opaque/semantic campus IDs; provider candidates remain external evidence |
| `persistent-identity-registry` | **pass** | duplicates=False providerIdentityLeaks=0 |
| `canonical-geometry-validity` | **pass** | rejected=0 needsReview=0 |
| `expanded-osm-layers` | **pass** | fixtureTypes=building,walkway,waterway |
| `osm-multipolygon-relations` | **pass** | relationPolygons=1 |
| `overture-public-api` | **pass** | adapter and fallback use documented package entry points |
| `overture-candidate-review` | **warning** | provider is blocked; no Overture coverage conclusion is made |
| `rights-gate` | **warning** | uncertainSources=1 canonicalLeaks=0 |
| `generated-luau-freshness` | **pass** | path=C:\Users\Dian\Documents\Vaults\Fensalir\uplb_roblox\src\Shared\Generated\CanonicalFeatures.lua |
| `generated-determinism` | **pass** | two in-memory generations compare equal |
| `first-25-review-package` | **pass** | rows=25; package remains pending human review |
| `schema-artifact-validation` | **pass** | canonical artifacts validate against production schemas |

## Measurements

```json
{
  "canonicalCount": 3,
  "geometryStates": {
    "uplb:building:baker-hall": "valid",
    "uplb:landmark:freedom-park": "valid",
    "uplb:landmark:oblation": "valid"
  },
  "overture": {
    "attemptedRelease": "2026-06-17.0",
    "packageVersion": "not-installed",
    "status": "blocked"
  },
  "registryCount": 3,
  "reviewPackageRows": 25,
  "sourceCount": 3
}
```

## Stop rule

Do not start the DEM, Blender, or persistent Roblox Studio phases until this report is reviewed and the decision is `pass`.
