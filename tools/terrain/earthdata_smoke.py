"""Run and record an anonymous Earthaccess/CMR search-only smoke test."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.geodata.io import write_json

from .acquire import DEFAULT_AOI, _import_earthaccess, search_product


def run_smoke(aoi_path: Path = DEFAULT_AOI) -> dict[str, Any]:
    earthaccess = _import_earthaccess()
    aoi_path = Path(aoi_path)
    try:
        aoi_label = aoi_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        aoi_label = aoi_path.as_posix()
    result: dict[str, Any] = {
        "status": "pass",
        "operation": "anonymous-cmr-search-only",
        "retrievalTimestamp": datetime.now(timezone.utc).isoformat(),
        "earthaccessVersion": str(getattr(earthaccess, "__version__", "unknown")),
        "aoiPath": aoi_label,
        "products": {},
        "credentialsUsed": False,
    }
    for product in ("srtm", "nasadem"):
        try:
            payload = search_product(product, aoi_path)
            payload.pop("_results", None)
            result["products"][product] = payload
        except Exception as exc:  # noqa: BLE001 - diagnostics are part of the evidence record
            result["status"] = "blocked"
            result["products"][product] = {
                "status": "blocked",
                "diagnostic": f"{type(exc).__name__}: {exc}",
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aoi", type=Path, default=DEFAULT_AOI)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_smoke(args.aoi)
    write_json(args.output, result)
    print(json.dumps({"status": result["status"], "output": str(args.output)}, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
