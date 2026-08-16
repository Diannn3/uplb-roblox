"""Public-API Overture provider adapter and candidate normalizer."""

from __future__ import annotations

import importlib.metadata
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Callable

from shapely.geometry import mapping

from .geometry import GeometryState, inspect_geometry
from .io import read_json, sha256
from .models import ProviderCandidate


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "unnamed"


def _name(properties: dict[str, Any], identifier: str) -> str:
    names = properties.get("names")
    if isinstance(names, dict):
        primary = names.get("primary")
        if isinstance(primary, dict) and primary.get("value"):
            return str(primary["value"])
        for value in names.values():
            if isinstance(value, dict) and value.get("value"):
                return str(value["value"])
            if isinstance(value, str):
                return value
    for key in ("name", "official_name"):
        if properties.get(key):
            return str(properties[key])
    return f"Overture building {identifier}"


class OvertureProvider:
    """Thin adapter around documented ``overturemaps`` public functions."""

    def __init__(self, reader_factory: Callable[..., Any] | None = None, release_resolver: Callable[[], str] | None = None) -> None:
        self._reader_factory = reader_factory
        self._release_resolver = release_resolver

    @staticmethod
    def package_version() -> str | None:
        try:
            return importlib.metadata.version("overturemaps")
        except importlib.metadata.PackageNotFoundError:
            return None

    def _reader(self) -> Callable[..., Any]:
        if self._reader_factory:
            return self._reader_factory
        try:
            from overturemaps import record_batch_reader
        except ImportError as exc:  # pragma: no cover - requires optional dependency
            raise RuntimeError("Overture support requires the optional overture dependency") from exc
        return record_batch_reader

    def resolve_release(self) -> str:
        if self._release_resolver:
            return self._release_resolver()
        try:
            from overturemaps import get_latest_release
        except ImportError:
            get_latest_release = None
        if get_latest_release is not None:
            return str(get_latest_release())
        # The package's documented STAC catalog is the release authority.  A
        # failure here is reported as blocked; callers must not silently fall
        # back to an unpinned release.
        try:
            with urllib.request.urlopen("https://stac.overturemaps.org/catalog.json", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest = payload.get("latest")
            if latest:
                return str(latest)
        except Exception as exc:  # pragma: no cover - network/provider path
            raise RuntimeError(f"Overture release resolution blocked: {exc}") from exc
        raise RuntimeError("Overture release resolution blocked: STAC catalog did not provide latest")

    def source_record(self, release: str, content_hash: str | None = None, accessed_at: str = "unrecorded") -> dict[str, Any]:
        return {
            "id": f"source:overture:buildings@{release}",
            "provider": "Overture Maps Foundation",
            "release": release,
            "packageVersion": self.package_version(),
            "sourceUrl": "https://docs.overturemaps.org/guides/buildings/",
            "license": "ODbL-1.0",
            "attribution": "Overture Maps Foundation and upstream contributors",
            "contentHash": content_hash,
            "accessedAt": accessed_at,
            "rightsStatus": "open-attribution-required",
            "intendedUse": ["building-footprint", "building-height", "conflation-candidate"],
            "status": "candidate-source",
        }

    def normalize_geojson(self, path: Path, release: str) -> tuple[tuple[ProviderCandidate, ...], dict[str, Any]]:
        payload = read_json(path)
        features: list[ProviderCandidate] = []
        for index, item in enumerate(payload.get("features", [])):
            properties = item.get("properties") or {}
            external_id = str(properties.get("id") or item.get("id") or index)
            name = _name(properties, external_id)
            geometry = item.get("geometry")
            geometry_inspection = inspect_geometry(geometry) if geometry else None
            if geometry_inspection and geometry_inspection.state == GeometryState.REJECTED:
                continue
            if geometry_inspection and geometry_inspection.geometry is not None:
                geometry = geometry_inspection.geometry
            features.append(
                ProviderCandidate(
                    id=f"candidate:overture:{external_id}",
                    provider="overture",
                    feature_type="building",
                    name=name,
                    geometry=geometry,
                    properties={
                        "heightM": properties.get("height"),
                        "levels": properties.get("num_floors"),
                        "overtureProperties": properties,
                        **(
                            {
                                "geometryState": geometry_inspection.state.value,
                                "geometryReason": geometry_inspection.reason,
                                "originalGeometryHash": geometry_inspection.original_hash,
                                **({"repairedGeometryHash": geometry_inspection.repaired_hash} if geometry_inspection.repaired_hash else {}),
                            }
                            if geometry_inspection
                            else {}
                        ),
                    },
                    external_ids={"overture": external_id},
                    provenance=(f"source:overture:buildings@{release}",),
                    confidence={"position": "medium", "footprint": "medium", "height": "medium", "facade": "unknown"},
                )
            )
        return tuple(features), self.source_record(release, f"sha256:{sha256(path)}")

    def fetch_buildings(
        self,
        bbox: tuple[float, float, float, float],
        *,
        release: str | None = None,
        stac: bool = False,
        connect_timeout: int = 10,
        request_timeout: int = 60,
    ) -> tuple[tuple[ProviderCandidate, ...], dict[str, Any]]:
        release = release or self.resolve_release()
        reader = self._reader()("building", bbox=bbox, release=release, stac=stac, connect_timeout=connect_timeout, request_timeout=request_timeout)
        table = reader.read_all() if hasattr(reader, "read_all") else reader
        rows = table.to_pylist() if hasattr(table, "to_pylist") else list(table)
        features: list[ProviderCandidate] = []
        for index, row in enumerate(rows):
            properties = dict(row)
            geometry = properties.pop("geometry", None)
            if geometry is not None and not isinstance(geometry, dict):
                geometry = mapping(geometry)
            geometry_inspection = inspect_geometry(geometry) if geometry else None
            if geometry_inspection and geometry_inspection.state == GeometryState.REJECTED:
                continue
            if geometry_inspection and geometry_inspection.geometry is not None:
                geometry = geometry_inspection.geometry
            external_id = str(properties.pop("id", index))
            name = _name(properties, external_id)
            features.append(
                ProviderCandidate(
                    id=f"candidate:overture:{external_id}",
                    provider="overture",
                    feature_type="building",
                    name=name,
                    geometry=geometry,
                    properties={
                        **properties,
                        **(
                            {
                                "geometryState": geometry_inspection.state.value,
                                "geometryReason": geometry_inspection.reason,
                                "originalGeometryHash": geometry_inspection.original_hash,
                                **({"repairedGeometryHash": geometry_inspection.repaired_hash} if geometry_inspection.repaired_hash else {}),
                            }
                            if geometry_inspection
                            else {}
                        ),
                    },
                    external_ids={"overture": external_id},
                    provenance=(f"source:overture:buildings@{release}",),
                    confidence={"position": "medium", "footprint": "medium", "height": "medium", "facade": "unknown"},
                )
            )
        return tuple(features), self.source_record(release)
