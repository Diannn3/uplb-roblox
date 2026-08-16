"""Time-boxed Overture client and direct-cloud/GeoParquet probes.

The command never commits downloaded provider data.  It records only status,
diagnostics, and a hash when a bounded probe succeeds.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .io import read_json, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BBOX = ROOT / "research" / "campus_bbox.json"
DEFAULT_REPORT = ROOT / "research" / "results" / "overture_fallback_probe.json"
DEFAULT_RAW = ROOT / "data" / "raw" / "overture_buildings_probe.geojson"


def _diagnostic(result: subprocess.CompletedProcess[str]) -> str:
    lines = (result.stderr or result.stdout or "").splitlines()
    return next((line.strip() for line in reversed(lines) if line.strip()), "no diagnostic output")


def probe_cli(cli: str | None, bbox: tuple[float, float, float, float], output: Path, timeout: int) -> dict[str, Any]:
    executable = cli or os.environ.get("OVERTUREMAPS_BIN") or shutil.which("overturemaps")
    attempt: dict[str, Any] = {"method": "official-cli", "status": "not-run"}
    if not executable:
        attempt["details"] = "overturemaps executable not found; provide --cli or OVERTUREMAPS_BIN."
        return attempt
    west, south, east, north = bbox
    command = [executable, "download", f"--bbox={west},{south},{east},{north}", "-f", "geojson", "--type=building", "-o", str(output)]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        if output.exists() and output.stat().st_size == 0:
            output.unlink()
        attempt.update(status="timeout", details=f"CLI exceeded {timeout}s timeout.")
        return attempt
    except OSError as exc:
        if output.exists() and output.stat().st_size == 0:
            output.unlink()
        attempt.update(status="blocked", details=f"CLI could not start: {exc}")
        return attempt
    if result.returncode != 0:
        attempt.update(status="blocked", exitCode=result.returncode, details=_diagnostic(result))
        if output.exists() and output.stat().st_size == 0:
            output.unlink()
        return attempt
    if not output.exists() or output.stat().st_size == 0:
        if output.exists() and output.stat().st_size == 0:
            output.unlink()
        attempt.update(status="blocked", details="CLI returned success without a non-empty output file.")
        return attempt
    attempt.update(status="validated", outputHash=f"sha256:{sha256(output)}", bytes=output.stat().st_size)
    return attempt


def probe_direct(python: str | None, release: str, bbox: tuple[float, float, float, float], timeout: int) -> dict[str, Any]:
    executable = python or os.environ.get("OVERTURE_PYTHON") or sys.executable
    west, south, east, north = bbox
    # Keep this probe on the package's documented public path.  ``stac=False``
    # exercises the direct cloud/GeoParquet path without importing private
    # package implementation details.
    code = (
        "from overturemaps import record_batch_reader; "
        f"reader=record_batch_reader('building', bbox=({west!r},{south!r},{east!r},{north!r}), "
        f"release={release!r}, stac=False, connect_timeout=3, request_timeout={timeout}); "
        "table=reader.read_all() if hasattr(reader, 'read_all') else reader; "
        "count=getattr(table, 'num_rows', None); "
        "print(int(count if count is not None else len(table)))"
    )
    attempt: dict[str, Any] = {"method": "direct-s3-geoparquet", "status": "not-run", "release": release}
    try:
        result = subprocess.run([executable, "-c", code], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        attempt.update(status="timeout", details=f"Direct cloud probe exceeded {timeout}s timeout.")
        return attempt
    except OSError as exc:
        attempt.update(status="blocked", details=f"Direct probe could not start: {exc}")
        return attempt
    if result.returncode != 0:
        attempt.update(status="blocked", exitCode=result.returncode, details=_diagnostic(result))
        return attempt
    count = (result.stdout or "").strip().splitlines()[-1] if (result.stdout or "").strip() else ""
    attempt.update(status="validated", rows=int(count))
    return attempt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", type=Path, default=DEFAULT_BBOX)
    parser.add_argument("--cli")
    parser.add_argument("--python")
    parser.add_argument("--release", default="2026-06-17.0")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    args = parser.parse_args()
    bbox_payload = read_json(args.bbox)
    bbox = (bbox_payload["west"], bbox_payload["south"], bbox_payload["east"], bbox_payload["north"])
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    attempts = [
        probe_cli(args.cli, bbox, args.raw_output, args.timeout),
        probe_direct(args.python, args.release, bbox, args.timeout),
    ]
    successful = [attempt for attempt in attempts if attempt["status"] == "validated"]
    report = {
        "version": 1,
        "bbox": {"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]},
        "attempts": attempts,
        "decision": "validated" if successful else "blocked",
        "notes": [
            "A blocked provider probe is not evidence that Overture has no coverage.",
            "Raw provider output remains gitignored and is deleted when a failed CLI creates an empty file.",
        ],
    }
    write_json(args.report, report)
    print(__import__("json").dumps(report, indent=2, sort_keys=True))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
