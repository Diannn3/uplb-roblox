# Wave 02 Local LLM Handoff

Apply this bundle only to the exact source commit:

`43cb34ad567ebbdecccee258413351fa00658dda`

Recommended branch:

`feat/modeling-wave02-evidence-integration`

The bundle's `apply_wave02.py` verifies the source HEAD and clean working tree, copies the overlay, then regenerates the scene-backed Baker placement binding on the local checkout. It does **not** commit or push.

After application, inspect the diff and run:

```powershell
python -m tools.modeling.wave02 --check --check-freshness
python -m tools.modeling.pipeline --check
python -m pytest -q tests/modeling
python -m pytest -q
python -m compileall -q tools tests
```

Do not mark the Blender or Roblox gates passed unless those stages actually run. The ChatGPT build host used for this implementation did not contain Blender or Roblox Studio.
