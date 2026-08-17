"""Credential-safe capability checks for the world-generation toolchain."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


def _blender_probe() -> dict[str, Any]:
    executable = shutil.which("blender") or shutil.which("blender.exe")
    if not executable:
        return {"available": False, "version": None, "executable": None, "diagnostic": "Blender executable was not found on PATH"}
    command = [executable, "--background", "--python-exit-code", "10", "--python-expr", "import bpy; print(bpy.app.version_string)"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "version": None, "executable": executable, "diagnostic": f"Blender probe failed: {exc.__class__.__name__}"}
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    version = None
    for line in output.splitlines():
        if line.strip().startswith("Blender"):
            version = line.strip()
            break
    return {
        "available": result.returncode == 0,
        "version": version,
        "executable": executable,
        "diagnostic": None if result.returncode == 0 else "Blender probe returned a non-zero exit code",
    }


def _earthdata_probe() -> dict[str, Any]:
    try:
        import earthaccess  # type: ignore[import-not-found]
    except ImportError:
        return {"libraryAvailable": False, "authenticated": False, "diagnostic": "earthaccess is not installed; install the earthdata extra"}
    netrc_paths = [Path.home() / ".netrc", Path.home() / "_netrc"]
    credentials_present = any(path.exists() and path.stat().st_size > 0 for path in netrc_paths) or bool(
        os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD")
    )
    return {
        "libraryAvailable": True,
        "authenticated": credentials_present,
        "diagnostic": None if credentials_present else "configure Earthdata Login via .netrc/_netrc or EARTHDATA_USERNAME/EARTHDATA_PASSWORD",
    }


def _roblox_probe() -> dict[str, Any]:
    return {"configured": False, "diagnostic": "Roblox Studio MCP is not exposed in this environment"}


def build_preflight(
    *,
    blender_probe: Callable[[], dict[str, Any]] | None = None,
    earthdata_probe: Callable[[], dict[str, Any]] | None = None,
    roblox_probe: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    python_version = ".".join(map(str, sys.version_info[:3]))
    return {
        "python": {
            "version": python_version,
            "required": "3.12+",
            "ready": sys.version_info >= (3, 12),
        },
        "blender": (blender_probe or _blender_probe)(),
        "earthdata": (earthdata_probe or _earthdata_probe)(),
        "robloxMcp": (roblox_probe or _roblox_probe)(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build_preflight(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
