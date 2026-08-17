from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _obj_stats(path: Path) -> dict[str, int]:
    vertices = 0
    faces = 0
    triangle_equivalent = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            vertices += 1
        elif line.startswith("f "):
            faces += 1
            triangle_equivalent += max(len(line.split()) - 3, 1)
    return {"vertices": vertices, "faces": faces, "triangleEquivalent": triangle_equivalent}


def build_prototype_asset_manifest() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    baker = ROOT / "assets" / "generated" / "prototypes" / "baker-hall-massing.obj"
    if baker.exists():
        records.append(
            {
                "id": "asset:prototype:baker-hall-massing",
                "kind": "building-massing",
                "featureId": "uplb:building:baker-hall",
                "file": baker.relative_to(ROOT).as_posix(),
                "sha256": _sha256(baker),
                "rights": "project-generated-from-reviewed-canonical-footprint",
                "productionDisposition": "NON_PRODUCTION_REFERENCE",
                "geometry": _obj_stats(baker),
                "sourceEvidence": [
                    "data/modeling/reference/baker-canonical-snapshot.geojson",
                    "data/modeling/building-specs/baker-hall.v0.1.json",
                ],
            }
        )
    proto_dir = ROOT / "assets" / "uplb-kit" / "prototypes"
    if proto_dir.exists():
        for path in sorted(proto_dir.glob("*.obj")):
            stable = path.stem.replace("_", ":", 1)
            records.append(
                {
                    "id": f"asset:kit-prototype:{path.stem}",
                    "kind": "architecture-kit-dimension-prototype",
                    "file": path.relative_to(ROOT).as_posix(),
                    "sha256": _sha256(path),
                    "rights": "project-generated",
                    "productionDisposition": "NON_PRODUCTION_REFERENCE",
                    "geometry": _obj_stats(path),
                    "sourceEvidence": ["data/modeling/architecture-kit-v0.1.json"],
                    "notes": f"Stable source component is represented by prototype filename {stable!r}; visual design is unverified.",
                }
            )
    return {
        "schemaVersion": "uplb-modeling-prototype-assets-v0.1",
        "status": "prototype-only",
        "records": records,
    }


def write_prototype_asset_manifest(path: Path = ROOT / "assets" / "manifests" / "modeling-prototypes.json") -> dict[str, Any]:
    manifest = build_prototype_asset_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
