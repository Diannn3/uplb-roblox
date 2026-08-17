# UPLB Asset Architecture

## Goal

Turn third-party/open asset sources into a controlled UPLB-specific library instead of letting the project become a random collection of downloaded models.

## Recommended structure

```text
assets/
├── external/
│   ├── kenney/
│   ├── quaternius/
│   ├── polyhaven/
│   └── research-only/
├── uplb-kit/
│   ├── architecture/
│   │   ├── windows/
│   │   ├── doors/
│   │   ├── concrete-columns/
│   │   ├── sunshades/
│   │   ├── roof-edges/
│   │   ├── railings/
│   │   ├── stairs/
│   │   ├── covered-walkways/
│   │   └── facade-panels/
│   ├── roads/
│   ├── street-furniture/
│   ├── signage/
│   ├── vegetation/
│   └── utilities/
└── manifests/
    ├── assets.json
    └── licenses/
```

## Rules

1. Every adopted asset gets a stable project ID.
2. Store original source URL, license, original file hash, import date, modifications, triangle count, collision policy, and intended use.
3. Prefer CC0 assets for anything likely to be committed to a public repository.
4. Keep GPL/research-code tools separate from exported game assets.
5. Roblox Creator Store assets must be inspected for scripts before use.
6. Procedural generators should be deterministic: same input + seed → same output.
7. Landmark buildings remain custom/verified assets; generic kits are for context and reusable components.
8. Do not let Blender, Roblox Studio, or a downloaded kit become the source of truth. The source remains the Git-controlled scene/asset specification.

## Suggested first UPLB component families

- 1970s concrete academic facade
- modern glass/concrete academic facade
- covered walkway
- jalousie/window families
- concrete column families
- sunshade/brise-soleil families
- campus railings
- standard stairs/ramps
- benches
- lamp posts
- bollards
- campus signage mounts
- curb/sidewalk pieces
- generic tropical vegetation pools
