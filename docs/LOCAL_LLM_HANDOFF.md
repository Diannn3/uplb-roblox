# Local LLM Handoff

## Base revision

This implementation was prepared against:

- repository: `Diannn3/uplb-roblox`
- branch: `feat/approved-roblox-validation-v0-1`
- commit: `b7a80eb06022241e4ffd85427e38d539dbb2c406`

The execution container could not resolve `github.com`, so a literal `git clone`
was unavailable. Repository state and exact base files were read through the
connected GitHub API instead. The ZIP therefore contains an **apply-ready patch
and overlay**, not `.git` history.

## Apply

From a clean checkout of the base commit/branch:

```powershell
git status
# must be clean

git apply --check implementation.patch
git apply implementation.patch

python -m pip install -e ".[dev,worldgen]"
python -m pytest -q tests/modeling
python -m tools.modeling.pipeline --check --generate-prototypes --write-report
python -m pytest -q
```

Review generated files, then commit normally.

## Suggested branch

`feat/campus-content-production-foundation`

## Suggested commits

1. `feat: add campus model source and production registries`
2. `feat: define uplb architecture kit v0.1`
3. `feat: add deterministic building prototype tooling`
4. `test: validate modeling registries and prototype generation`
5. `docs: define campus modeling and source recovery workflow`
