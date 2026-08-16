"""Explicitly promote one local provider candidate into campus canonical data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .identity import IdentityRegistry
from .io import write_feature_collection
from .review import DEFAULT_CANDIDATE_ROOT, DEFAULT_CANONICAL, DEFAULT_REGISTRY, _canonical_item, _read_canonical, find_candidate


def promote(
    candidate_id: str,
    *,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    canonical_path: Path = DEFAULT_CANONICAL,
    promoted_at: str | None = None,
) -> dict[str, object]:
    candidate = find_candidate(candidate_id, candidate_root)
    if candidate is None:
        raise FileNotFoundError(f"candidate not found in local snapshots: {candidate_id}")
    registry = IdentityRegistry.load(registry_path)
    feature = registry.promote_candidate(candidate)
    registry.save(registry_path)
    payload = _read_canonical(canonical_path)
    features = [item for item in payload.get("features", []) if item.get("id") != feature.id]
    item = _canonical_item(feature)
    if promoted_at:
        item.setdefault("properties", {})["promotionRevision"] = promoted_at
    features.append(item)
    write_feature_collection(
        canonical_path,
        features,
        **{key: value for key, value in payload.items() if key not in {"type", "features"}},
    )
    return {
        "candidateId": candidate_id,
        "canonicalId": feature.id,
        "canonicalCount": len(features),
        "registryPath": str(registry_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_id")
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--promoted-at")
    args = parser.parse_args()
    print(json.dumps(promote(args.candidate_id, candidate_root=args.candidate_root, registry_path=args.registry, canonical_path=args.canonical, promoted_at=args.promoted_at), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
