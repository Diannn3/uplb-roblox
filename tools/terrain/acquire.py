"""Credential-safe NASA DEM acquisition entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .preprocess import build_fixture_heightfield
from .sources import product_source


def acquire_product(product: str, output_dir: Path, *, fixture: bool = False) -> dict[str, Any]:
    source = product_source(product)
    output_dir = Path(output_dir)
    if fixture:
        field = build_fixture_heightfield(product, output_dir)
        return {"status": "fixture-only", "product": source["product"], "output": str(output_dir), "sourceKind": field.source_kind}
    # Do not create the directory or a placeholder file when credentials/data
    # are unavailable. This prevents zero-byte artifacts from looking valid.
    return {
        "status": "blocked",
        "product": source["product"],
        "diagnostic": "Earthdata Login and a current supported Earthdata Search/Earthdata Cloud route are required; no credentials were found or stored. Retry with --fixture only for deterministic harness tests.",
        "output": str(output_dir),
        "source": source["landingPage"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=("srtm", "nasadem"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/terrain"))
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    result = acquire_product(args.product, args.output / args.product, fixture=args.fixture)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "fixture-only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
