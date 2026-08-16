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
DEFAULT_PRIORITY_REVIEW = ROOT / "data" / "reviews" / "vertical-slice-review.json"
VERIFICATION_VALUES = {"unknown", "provisional", "source-supported", "human-reviewed", "verified", "conflicting"}
PRIORITY_CATEGORY_ORDER = ("hero/reference", "ordinary building", "road/intersection", "walkway/pedestrian", "environmental")


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


def _priority_package(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload.get("rows"), list):
        raise ValueError(f"priority review package must contain rows: {path}")
    return payload


def _write_priority_package(path: Path, package: dict[str, Any]) -> None:
    package["rows"] = sorted(package.get("rows", []), key=lambda row: (PRIORITY_CATEGORY_ORDER.index(row.get("category", "environmental")) if row.get("category") in PRIORITY_CATEGORY_ORDER else len(PRIORITY_CATEGORY_ORDER), str(row.get("candidateId", ""))))
    package["humanReviewStatus"] = "complete" if package["rows"] and all(row.get("currentDecision") != "pending" for row in package["rows"]) else "pending"
    write_json(path, package)


def _record_priority_history(row: dict[str, Any], action: str, changes: dict[str, Any], reviewed_at: str | None) -> None:
    history = row.setdefault("reviewHistory", [])
    history.append(
        {
            "action": action,
            "at": reviewed_at,
            "changes": changes,
            "previousDecision": row.get("currentDecision", "pending"),
        }
    )


def decide_priority(
    review_id: str,
    decision: str,
    *,
    review_path: Path = DEFAULT_PRIORITY_REVIEW,
    reviewed_at: str | None = None,
    review_method: str | None = None,
    evidence_refs: Iterable[str] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    """Record a human decision without promoting or deleting source evidence."""

    if decision not in {"accept", "reject"}:
        raise ValueError("priority decision must be accept or reject")
    package = _priority_package(review_path)
    row = next((item for item in package["rows"] if item.get("candidateId") == review_id), None)
    if row is None:
        raise KeyError(f"priority review not found: {review_id}")
    previous = row.get("currentDecision", "pending")
    row["currentDecision"] = decision
    row["reviewStatus"] = "reviewed"
    changes: dict[str, Any] = {"currentDecision": {"from": previous, "to": decision}}
    if reason is not None:
        row["reviewNotes"] = reason
        changes["reviewNotes"] = reason
    refs = sorted({str(ref) for ref in evidence_refs if str(ref)})
    if reviewed_at or review_method or refs:
        if not (reviewed_at and review_method and refs):
            raise ValueError("reviewedAt, reviewMethod, and at least one evidenceRef are required together")
        row["review"] = {"reviewedAt": reviewed_at, "reviewMethod": review_method, "evidenceRefs": refs}
        changes["review"] = row["review"]
    _record_priority_history(row, decision, changes, reviewed_at)
    _write_priority_package(review_path, package)
    return {"candidateId": review_id, "decision": decision, "humanReviewStatus": package["humanReviewStatus"]}


def modify_priority(
    review_id: str,
    *,
    review_path: Path = DEFAULT_PRIORITY_REVIEW,
    name: str | None = None,
    aliases: Iterable[str] | None = None,
    canonical_id: str | None = None,
    verification: dict[str, str] | None = None,
    selected_geometry_source: str | None = None,
    notes: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Apply an explicit correction while retaining the original provider record."""

    package = _priority_package(review_path)
    row = next((item for item in package["rows"] if item.get("candidateId") == review_id), None)
    if row is None:
        raise KeyError(f"priority review not found: {review_id}")
    changes: dict[str, Any] = {}
    if name is not None:
        row.setdefault("sourceName", row.get("name"))
        row["name"] = name
        changes["name"] = name
    if aliases is not None:
        row.setdefault("sourceAliases", list(row.get("aliases", [])))
        row["aliases"] = list(dict.fromkeys(str(alias) for alias in aliases))
        changes["aliases"] = row["aliases"]
    if canonical_id is not None:
        row["registryMatch"] = canonical_id
        row["canonicalIdentityCorrection"] = canonical_id
        changes["canonicalIdentity"] = canonical_id
    if verification is not None:
        invalid = {key: value for key, value in verification.items() if value not in VERIFICATION_VALUES}
        if invalid:
            raise ValueError(f"unsupported verification values: {invalid}")
        row["verification"] = dict(sorted(verification.items()))
        changes["verification"] = row["verification"]
    if selected_geometry_source is not None:
        row["selectedGeometrySource"] = selected_geometry_source
        changes["selectedGeometrySource"] = selected_geometry_source
    if notes is not None:
        row["reviewNotes"] = notes
        changes["reviewNotes"] = notes
    if not changes:
        raise ValueError("modify requires at least one explicit correction")
    row["reviewStatus"] = "reviewed"
    _record_priority_history(row, "modify", changes, reviewed_at)
    _write_priority_package(review_path, package)
    return {"candidateId": review_id, "changes": changes, "humanReviewStatus": package["humanReviewStatus"]}


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
    parser.add_argument("action", choices=("list", "show", "accept", "reject", "modify"))
    parser.add_argument("review_id", nargs="?")
    parser.add_argument("--review-file", type=Path, default=DEFAULT_REVIEW_FILE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--reviewed-at")
    parser.add_argument("--reason")
    parser.add_argument("--priority", action="store_true", help="operate on the authoritative vertical-slice package")
    parser.add_argument("--name")
    parser.add_argument("--alias", action="append", dest="aliases")
    parser.add_argument("--aliases", nargs="+", dest="aliases_many")
    parser.add_argument("--canonical-id")
    parser.add_argument("--canonical-identity", dest="canonical_identity")
    parser.add_argument("--verification", action="append", help="property=value; may be repeated")
    parser.add_argument("--selected-geometry-source")
    parser.add_argument("--notes")
    parser.add_argument("--review-method")
    parser.add_argument("--evidence-ref", action="append", default=[])
    args = parser.parse_args()
    if args.priority:
        priority_path = args.review_file if args.review_file != DEFAULT_REVIEW_FILE else DEFAULT_PRIORITY_REVIEW
        package = _priority_package(priority_path)
        if args.action == "list":
            _print(package["rows"])
            return 0
        if not args.review_id:
            parser.error(f"{args.action} requires <candidate-id> in priority mode")
        if args.action == "show":
            row = next((item for item in package["rows"] if item.get("candidateId") == args.review_id), None)
            if row is None:
                parser.error(f"priority review not found: {args.review_id}")
            _print(row)
            return 0
        if args.action == "modify":
            corrections: dict[str, str] = {}
            for raw in args.verification or []:
                if raw.lstrip().startswith("{"):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        parser.error(f"--verification JSON is invalid: {exc}")
                    if not isinstance(parsed, dict):
                        parser.error("--verification JSON must be an object")
                    corrections.update({str(key): str(value) for key, value in parsed.items()})
                else:
                    if "=" not in raw:
                        parser.error("--verification requires property=value or a JSON object")
                    key, value = raw.split("=", 1)
                    corrections[key] = value
            aliases = [*(args.aliases or []), *(args.aliases_many or [])] or None
            notes = args.notes if args.notes is not None else args.reason
            canonical_id = args.canonical_id if args.canonical_id is not None else args.canonical_identity
            _print(modify_priority(args.review_id, review_path=priority_path, name=args.name, aliases=aliases, canonical_id=canonical_id, verification=corrections or None, selected_geometry_source=args.selected_geometry_source, notes=notes, reviewed_at=args.reviewed_at))
            return 0
        _print(decide_priority(args.review_id, args.action, review_path=priority_path, reviewed_at=args.reviewed_at, review_method=args.review_method, evidence_refs=args.evidence_ref, reason=args.reason))
        return 0
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
    if args.action == "modify":
        parser.error("modify requires --priority")
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
