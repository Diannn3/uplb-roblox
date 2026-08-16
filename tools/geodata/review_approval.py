"""Freeze an explicit, auditable vertical-slice review version.

The pending priority package remains the editable working file.  This module
creates an immutable review snapshot with package/candidate hashes and an
explicit project-owner approval record.  It never promotes candidates to the
canonical dataset.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .io import read_json, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = ROOT / "data" / "reviews" / "vertical-slice-review.json"
DEFAULT_OUTPUT = ROOT / "data" / "reviews" / "approved" / "vertical-slice-review-v1.json"


def _hash_file(path: Path) -> str:
    return f"sha256:{sha256(path)}"


def _default_verification(row: dict[str, Any]) -> dict[str, str]:
    """Return conservative POC verification, leaving unknown detail unknown."""

    feature_type = str(row.get("featureType", ""))
    geometry_status = str(row.get("geometryStatus", ""))
    confidence = row.get("confidence") or {}
    is_point = (row.get("sourceGeometry") or {}).get("type") in {"Point", "MultiPoint"}
    return {
        "identity": "human-reviewed",
        "position": "human-reviewed",
        "footprint": "unknown" if is_point else ("source-supported" if geometry_status in {"valid", "repaired-safe"} else "unknown"),
        "height": "source-supported" if str(confidence.get("height", "unknown")) != "unknown" and feature_type == "building" else "unknown",
        "facade": "unknown",
        "interior": "unknown",
    }


def freeze_review_v1(
    package_path: Path = DEFAULT_PACKAGE,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    approved_at: str | None = None,
    reviewer: str = "project-owner",
    notes: str = (
        "Phase 1 POC approval assumption: accepted rows are reviewed for identity, "
        "position, and usable greybox geometry; facade/interior/detail accuracy remains unknown "
        "and no survey-grade claim is made."
    ),
) -> dict[str, Any]:
    """Create or replace the versioned v1 approval snapshot."""

    package = read_json(package_path)
    rows = package.get("rows")
    if not isinstance(rows, list) or len(rows) != 25:
        raise ValueError("the vertical-slice package must contain exactly 25 rows before approval")
    if package.get("missingRequiredHeroes"):
        raise ValueError("cannot approve a package with missing required heroes")
    timestamp = approved_at or datetime.now().astimezone().isoformat(timespec="seconds")
    candidate_hash = package.get("sourceHash")
    if not isinstance(candidate_hash, str) or not candidate_hash.startswith("sha256:"):
        raise ValueError("the package must carry a sha256: candidate source hash")

    approved_rows: list[dict[str, Any]] = []
    for source_row in rows:
        row = copy.deepcopy(source_row)
        row["currentDecision"] = "accept"
        row["reviewStatus"] = "reviewed"
        verification = _default_verification(row)
        verification.update({str(key): str(value) for key, value in (row.get("verification") or {}).items()})
        row["verification"] = dict(sorted(verification.items()))
        row["reviewer"] = reviewer
        row["reviewerProvenance"] = {
            "reviewer": reviewer,
            "sourcePackagePath": package_path.relative_to(ROOT).as_posix() if package_path.is_relative_to(ROOT) else package_path.as_posix(),
            "sourcePackageHash": _hash_file(package_path),
            "sourceCandidateHash": candidate_hash,
        }
        row["reviewNotes"] = row.get("reviewNotes") or notes
        review = dict(row.get("review") or {})
        review.update(
            {
                "reviewedAt": review.get("reviewedAt") or timestamp,
                "reviewMethod": review.get("reviewMethod") or "project-owner",
                "evidenceRefs": sorted(
                    {
                        *(str(value) for value in review.get("evidenceRefs", []) if str(value)),
                        package_path.relative_to(ROOT).as_posix() if package_path.is_relative_to(ROOT) else package_path.as_posix(),
                        candidate_hash,
                    }
                ),
            }
        )
        row["review"] = review
        history = list(row.get("reviewHistory") or [])
        history.append(
            {
                "action": "approve",
                "at": timestamp,
                "changes": {"currentDecision": {"from": source_row.get("currentDecision", "pending"), "to": "accept"}},
                "previousDecision": source_row.get("currentDecision", "pending"),
                "reviewer": reviewer,
            }
        )
        row["reviewHistory"] = history
        approved_rows.append(row)

    snapshot = copy.deepcopy(package)
    snapshot.update(
        {
            "reviewVersion": "v1",
            "approvalStatus": "approved",
            "reviewer": reviewer,
            "approvedAt": timestamp,
            "sourcePackagePath": package_path.relative_to(ROOT).as_posix() if package_path.is_relative_to(ROOT) else package_path.as_posix(),
            "sourcePackageHash": _hash_file(package_path),
            "sourceCandidateHash": candidate_hash,
            "notes": notes,
            "humanReviewStatus": "complete",
            "rows": approved_rows,
        }
    )
    write_json(output_path, snapshot)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-at")
    parser.add_argument("--reviewer", default="project-owner")
    args = parser.parse_args()
    snapshot = freeze_review_v1(args.package, args.output, approved_at=args.approved_at, reviewer=args.reviewer)
    print(json.dumps({key: snapshot[key] for key in ("reviewVersion", "approvalStatus", "reviewer", "approvedAt", "sourcePackageHash", "sourceCandidateHash")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
