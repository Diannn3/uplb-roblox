# Research reproducibility

This directory contains research-only scripts, fixtures, and source manifests for the UPLB Roblox master plan. It does **not** generate production Roblox world content.

- `raw/` is gitignored and reserved for replaceable public/authorized downloads.
- Never store Google Maps/Street View imagery, restricted LiDAR, credentials, login-gated institutional plans, or unlicensed photos here.
- `sources.json` is the dated source register.
- `upstream_repositories.json` pins the related UPLB projects audited by this research.
- `campus_bbox.json` is a research AOI, not an official campus boundary.

Run the deterministic coordinate test with `python research/scripts/coordinate_transform.py`.
Run `python research/scripts/osm_overture_compare.py --fetch` only in a network-enabled environment after installing the official `overturemaps` CLI. The harness hashes retained raw inputs and records summary metrics. The 2026-08-17 run fetched OSM successfully; Overture remains pending because the installed client failed while resolving its STAC catalog with HTTP 404, which is not evidence of missing Overture coverage.

Provider fetch failures are recorded in `research/results/osm_overture_comparison.json`; `--fetch` exits nonzero when either provider fails so the retry is visible to automation.

Install the coordinate-test dependency with `python -m pip install -r research/requirements.txt`.
