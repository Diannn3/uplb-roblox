"""Inspect and explicitly decide provider conflation reviews.

The command is deliberately review-first: listing and showing reviews are
read-only, while accept/reject are explicit mutations of the review file.  An
accept also promotes or updates the selected candidate only when its provider
record is available locally.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .identity import IdentityRegistry
from .io import read_json, write_feature_collection, write_json
from .models import CanonicalFeature, ProviderCandidate


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REVIEW_FILE = ROOT / "data" / "canonical" / "review-decisions.json"
DEFAULT_REGISTRY = ROOT / "data" / "canonical" / "identity-registry.json"
DEFAULT_CANONICAL = ROOT / "data" / "canonical" / "features.geojson"
DEFAULT_CANDIDATE_ROOT = ROOT / "data" / "candidates"


def _review_rows(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    rows = payload.get("decisions", payload.get("reviews", []))
    if not isinstance(rows, list):
        raise ValueError(f"review file must contain a decisions/reviews list: {path}")
    return [dict(row) for row in rows]


def _candidate_from_geojson(item: dict[str, Any]) -> ProviderCandidate:
    properties = item.get("properties") or {}
    attributes = properties.get("attributes") or {}
    return ProviderCandidate(
        id=str(item.get("id") or properties.get("id")),
        provider=str(properties.get("provider") or "unknown"),
        feature_type=str(properties.get("featureType") or "unknown"),
        name=str(properties.get("name") or item.get("id") or "Unnamed candidate"),
        geometry=item.get("geometry"),
        aliases=tuple(str(value) for value in properties.get("aliases", [])),
        properties=dict(attributes),
        external_ids={str(key): str(value) for key, value in (properties.get("externalIds") or {}).items()},
        provenance=tuple(str(value) for value in properties.get("provenance", [])),
        confidence={str(key): str(value) for key, value in (properties.get("confidence") or {}).items()},
        verification_status=str(properties.get("verificationStatus") or "candidate"),
    )


def find_candidate(candidate_id: str, candidate_root: Path = DEFAULT_CANDIDATE_ROOT) -> ProviderCandidate | None:
    if not candidate_root.exists():
        return None
    for path in sorted(candidate_root.rglob("*.geojson")):
        payload = read_json(path)
        for item in payload.get("features", []):
            if str(item.get("id")) == candidate_id:
                return _candidate_from_geojson(item)
    return None


def _read_canonical(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"type": "FeatureCollection", "canonicalVersion": "canonical-v1", "features": []}
    payload = read_json(path)
    if payload.get("type") != "FeatureCollection":
        raise ValueError(f"canonical output is not a FeatureCollection: {path}")
    return payload


def _canonical_item(feature: CanonicalFeature) -> dict[str, Any]:
    return feature.to_geojson_feature()


def _upsert_canonical(path: Path, feature: CanonicalFeature) -> int:
    payload = _read_canonical(path)
    features = [item for item in payload.get("features", []) if item.get("id") != feature.id]
    features.append(_canonical_item(feature))
    write_feature_collection(
        path,
        features,
        **{key: value for key, value in payload.items() if key not in {"type", "features"}},
    )
    return len(features)


def _write_reviews(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    write_json(path, {"version": 2, "decisions": sorted(rows, key=lambda row: str(row.get("id", "")))})


def decide(
    review_id: str,
    decision: str,
    *,
    review_path: Path = DEFAULT_REVIEW_FILE,
    registry_path: Path = DEFAULT_REGISTRY,
    canonical_path: Path = DEFAULT_CANONICAL,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    reviewed_at: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be accept or reject")
    rows = _review_rows(review_path)
    row = next((item for item in rows if item.get("id") == review_id), None)
    if row is None:
        raise KeyError(f"review not found: {review_id}")
    row["decision"] = decision
    row["reviewStatus"] = "reviewed"
    if reviewed_at:
        row["reviewedAt"] = reviewed_at
    if reason:
        row["reason"] = reason

    promoted: CanonicalFeature | None = None
    canonical_count: int | None = None
    if decision == "accept":
        candidate_ids = row.get("candidateIds") or {}
        candidate_map = {
            str(provider): find_candidate(str(candidate_id), candidate_root)
            for provider, candidate_id in sorted(candidate_ids.items())
        }
        candidate = next((item for item in candidate_map.values() if item is not None), None)
        if candidate is None:
            candidate_id = next((str(value) for _, value in sorted(candidate_ids.items())), None)
            raise FileNotFoundError(
                f"accepted review references candidate {candidate_id!r}, but no local candidate snapshot contains it"
            )
        registry = IdentityRegistry.load(registry_path)
        canonical_id = row.get("canonicalId") or None
        promoted = registry.promote_candidate(candidate, canonical_id=canonical_id)
        for linked_candidate in candidate_map.values():
            if linked_candidate is None:
                continue
            for provider, external_id in linked_candidate.external_ids.items():
                registry.update_external_id(promoted.id, provider, external_id)
        row["canonicalId"] = promoted.id
        registry.save(registry_path)
        canonical_count = _upsert_canonical(canonical_path, promoted)
    _write_reviews(review_path, rows)
    return {
        "reviewId": review_id,
        "decision": decision,
        "canonicalId": promoted.id if promoted else row.get("canonicalId"),
        "canonicalCount": canonical_count,
    }


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "show", "accept", "reject"))
    parser.add_argument("review_id", nargs="?")
    parser.add_argument("--review-file", type=Path, default=DEFAULT_REVIEW_FILE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--reviewed-at")
    parser.add_argument("--reason")
    args = parser.parse_args()
    if args.action == "list":
        _print(_review_rows(args.review_file))
        return 0
    if not args.review_id:
        parser.error(f"{args.action} requires <review-id>")
    if args.action == "show":
        row = next((item for item in _review_rows(args.review_file) if item.get("id") == args.review_id), None)
        if row is None:
            parser.error(f"review not found: {args.review_id}")
        _print(row)
        return 0
    _print(
        decide(
            args.review_id,
            args.action,
            review_path=args.review_file,
            registry_path=args.registry,
            canonical_path=args.canonical,
            candidate_root=args.candidate_root,
            reviewed_at=args.reviewed_at,
            reason=args.reason,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
