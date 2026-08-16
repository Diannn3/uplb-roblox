"""Offline CI checks for the canonical geodata boundary."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .bootstrap import bootstrap
from .io import sha256
from .pipeline import build
from .schemas import validate_artifacts


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "geodata"


def _git_safety_errors() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    paths = [value.decode("utf-8") for value in result.stdout.split(b"\0") if value]
    errors: list[str] = []
    forbidden_suffixes = {".pem", ".p12", ".key", ".pfx", ".rbxl", ".rbxlx", ".rbxm", ".rbxmx", ".blend", ".fbx", ".glb", ".gltf", ".tif", ".tiff", ".las", ".laz"}
    for path in paths:
        normalized = path.replace("\\", "/")
        if (normalized.startswith("data/raw/") or normalized.startswith("research/raw/")) and not normalized.endswith("/.gitkeep"):
            errors.append(f"tracked raw provider input: {path}")
        if normalized.lower().endswith(tuple(forbidden_suffixes)):
            errors.append(f"tracked forbidden binary/geospatial artifact: {path}")
        if Path(path).name in {".env", "credentials.json", "service-account.json"}:
            errors.append(f"tracked credential-like file: {path}")
    return errors


def run() -> list[str]:
    errors = validate_artifacts(ROOT)
    errors.extend(_git_safety_errors())
    with tempfile.TemporaryDirectory() as directory:
        temp_root = Path(directory)
        bootstrap(raw_path=FIXTURE_ROOT / "osm-small.json", output_root=temp_root / "bootstrap", fixture_mode=True)
        outputs: list[tuple[Path, Path]] = []
        for index in (1, 2):
            output_root = temp_root / f"run-{index}"
            result = build(
                osm_path=FIXTURE_ROOT / "osm-small.json",
                output_dir=output_root / "canonical",
                fixture_path=ROOT / "research" / "fixtures" / "uplb_reference_points.geojson",
                accessed_at="2026-08-17",
                registry_path=ROOT / "data" / "canonical" / "identity-registry.json",
                area_path=ROOT / "data" / "areas" / "vertical-slice-v0.geojson",
                generated_path=output_root / "generated" / "CanonicalFeatures.lua",
                review_doc_path=output_root / "review.md",
            )
            if result["canonicalCount"] != 3:
                errors.append(f"fixture pipeline promoted {result['canonicalCount']} rows; expected 3")
            outputs.append((output_root / "canonical" / "features.geojson", output_root / "generated" / "CanonicalFeatures.lua"))
        for first, second in zip(outputs[0], outputs[1]):
            if sha256(first) != sha256(second):
                errors.append(f"nondeterministic generated artifact: {first.name}")
    return errors


def main() -> int:
    errors = run()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: offline geodata CI checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
