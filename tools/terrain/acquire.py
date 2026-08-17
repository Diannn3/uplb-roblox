"""Credential-safe NASA DEM acquisition through the official earthaccess API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.geodata.io import geometry_bbox, write_json

from .preprocess import build_fixture_heightfield
from .sources import product_source


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AOI = ROOT / "data" / "vertical-slices" / "v0.1" / "area.geojson"
MAX_GRANULES = 16


def _credentials_available() -> bool:
    netrc = [Path.home() / ".netrc", Path.home() / "_netrc"]
    return any(path.exists() and path.stat().st_size > 0 for path in netrc) or bool(
        os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD")
    )


def _import_earthaccess() -> Any:
    try:
        import earthaccess  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Earthdata Login acquisition is blocked because earthaccess is not installed; install the [earthdata] extra under Python 3.12+") from exc
    return earthaccess


def _aoi_bbox(path: Path) -> list[float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    bounds: list[tuple[float, float, float, float]] = []
    for feature in payload.get("features", []):
        bbox = geometry_bbox(feature.get("geometry"))
        if bbox:
            bounds.append(bbox)
    if not bounds:
        raise ValueError(f"AOI has no geometry: {path}")
    return [min(item[0] for item in bounds), min(item[1] for item in bounds), max(item[2] for item in bounds), max(item[3] for item in bounds)]


def _value(result: Any, *names: str) -> Any:
    if isinstance(result, dict):
        for name in names:
            if name in result:
                return result[name]
    for name in names:
        value = getattr(result, name, None)
        if value is not None:
            return value
    return None


def _result_bbox(result: Any) -> list[float] | None:
    value = _value(result, "bbox", "bounding_box", "boundingBox")
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [float(item) for item in value]
    if isinstance(value, dict):
        keys = {key.lower(): value[key] for key in value}
        if all(key in keys for key in ("west", "south", "east", "north")):
            return [float(keys["west"]), float(keys["south"]), float(keys["east"]), float(keys["north"])]
    return None


def _overlaps(left: list[float], right: list[float]) -> bool:
    return not (left[2] < right[0] or left[0] > right[2] or left[3] < right[1] or left[1] > right[3])


def _normalise_granule(result: Any, source: dict[str, Any], aoi: list[float]) -> dict[str, Any]:
    short_name = _value(result, "shortName", "short_name")
    version = _value(result, "version")
    bbox = _result_bbox(result)
    if str(short_name) != str(source["shortName"]):
        raise ValueError(f"Earthdata result short name mismatch: expected {source['shortName']}, got {short_name}")
    if str(version) != str(source["version"]):
        raise ValueError(f"Earthdata result version mismatch: expected {source['version']}, got {version}")
    if bbox is None or not _overlaps(aoi, bbox):
        raise ValueError("Earthdata result does not expose an overlapping bounding box")
    filename = _value(result, "filename", "file_name", "name")
    if not filename:
        links = _value(result, "data_links", "dataLinks")
        if callable(links):
            links = links()
        if isinstance(links, (list, tuple)) and links:
            filename = str(links[0]).rsplit("/", 1)[-1]
    return {
        "conceptId": _value(result, "conceptId", "concept_id") or "unknown",
        "shortName": str(short_name),
        "version": str(version),
        "bbox": bbox,
        "filename": str(filename) if filename else None,
    }


def search_product(
    product: str,
    aoi_path: Path = DEFAULT_AOI,
    *,
    earthaccess_client: Any | None = None,
    count: int = MAX_GRANULES,
) -> dict[str, Any]:
    source = product_source(product)
    client = earthaccess_client or _import_earthaccess()
    aoi = _aoi_bbox(aoi_path)
    results = list(
        client.search_data(
            short_name=source["shortName"],
            version=source["version"],
            bounding_box=aoi,
            count=count,
        )
    )
    if not results:
        raise RuntimeError(f"Earthdata search returned no {source['product']} granules overlapping the UPLB AOI")
    if len(results) > count or len(results) > MAX_GRANULES:
        raise RuntimeError(f"Earthdata search returned an unreasonable granule count: {len(results)}")
    granules = [_normalise_granule(result, source, aoi) for result in results]
    return {
        "status": "search-passed",
        "product": source["product"],
        "shortName": source["shortName"],
        "version": source["version"],
        "aoi": aoi,
        "granules": granules,
        "_results": results,
    }


def _cleanup_created(output_dir: Path, before: set[Path]) -> None:
    if not output_dir.exists():
        return
    for path in sorted(output_dir.rglob("*"), reverse=True):
        if path.is_file() and path not in before:
            path.unlink()
    for path in sorted(output_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if output_dir.exists() and not any(output_dir.iterdir()) and output_dir not in before:
        output_dir.rmdir()


def acquire_product(
    product: str,
    output_dir: Path,
    *,
    fixture: bool = False,
    aoi_path: Path = DEFAULT_AOI,
    earthaccess_client: Any | None = None,
    credentials_available: bool | None = None,
) -> dict[str, Any]:
    source = product_source(product)
    output_dir = Path(output_dir)
    if fixture:
        field = build_fixture_heightfield(product, output_dir)
        return {"status": "fixture-only", "product": source["product"], "output": str(output_dir), "sourceKind": field.source_kind}
    try:
        client = earthaccess_client or _import_earthaccess()
    except RuntimeError as exc:
        return {"status": "blocked", "product": source["product"], "diagnostic": str(exc), "output": str(output_dir), "source": source["landingPage"]}
    has_credentials = _credentials_available() if credentials_available is None else credentials_available
    if not has_credentials:
        return {
            "status": "blocked",
            "product": source["product"],
            "diagnostic": "Earthdata Login is required; configure .netrc/_netrc or EARTHDATA_USERNAME and EARTHDATA_PASSWORD. No credential values are read into project files.",
            "output": str(output_dir),
            "source": source["landingPage"],
        }
    before = {path for path in output_dir.rglob("*")} if output_dir.exists() else set()
    try:
        client.login()
        search = search_product(product, aoi_path, earthaccess_client=client)
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded = client.download(search["_results"], str(output_dir))
        files: list[dict[str, Any]] = []
        for item in downloaded or []:
            path = Path(item)
            if not path.exists() or path.stat().st_size == 0:
                raise RuntimeError("Earthdata download produced a missing or zero-byte file")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append({"filename": path.name, "path": path.relative_to(output_dir).as_posix(), "sizeBytes": path.stat().st_size, "sha256": f"sha256:{digest}"})
        if not files:
            raise RuntimeError("Earthdata download returned no files")
        manifest = {
            "product": source["product"],
            "shortName": source["shortName"],
            "version": source["version"],
            "retrievalTimestamp": datetime.now(timezone.utc).isoformat(),
            "queryAOI": search["aoi"],
            "landingPage": source["landingPage"],
            "granules": search["granules"],
            "files": files,
            "status": "downloaded",
        }
        write_json(output_dir / "acquisition-manifest.json", manifest)
        return {"status": "downloaded", "product": source["product"], "output": str(output_dir), "manifest": manifest}
    except Exception as exc:
        _cleanup_created(output_dir, before)
        diagnostic = re.sub(r"(?i)(password|token|secret)\s*[:=]\s*[^ ]+", r"\1=<redacted>", str(exc))
        return {
            "status": "blocked",
            "product": source["product"],
            "diagnostic": f"Earthdata acquisition did not complete: {exc.__class__.__name__}: {diagnostic}",
            "output": str(output_dir),
            "source": source["landingPage"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=("srtm", "nasadem"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/terrain"))
    parser.add_argument("--aoi", type=Path, default=DEFAULT_AOI)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    result = acquire_product(args.product, args.output / args.product, fixture=args.fixture, aoi_path=args.aoi)
    print(json.dumps({key: value for key, value in result.items() if key != "manifest"}, indent=2, sort_keys=True))
    return 0 if result["status"] in {"fixture-only", "downloaded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
