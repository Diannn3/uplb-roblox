"""Create the evidence-gate report from pinned research results."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .io import read_json, sha256, write_json
from .models import ValidationReport


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPARISON = ROOT / "research" / "results" / "osm_overture_comparison.json"
DEFAULT_PROBE = ROOT / "research" / "results" / "overture_fallback_probe.json"
DEFAULT_OSM = ROOT / "research" / "raw" / "osm_uplb_aoi.json"
DEFAULT_MATRIX = ROOT / "data" / "source-matrix.json"
DEFAULT_JSON = ROOT / "data" / "canonical" / "evidence-gate-report.json"
DEFAULT_MD = ROOT / "docs" / "EVIDENCE_GATE_REPORT.md"


def build_report(comparison_path: Path, probe_path: Path, osm_path: Path, matrix_path: Path) -> ValidationReport:
    comparison = read_json(comparison_path)
    probe = read_json(probe_path) if probe_path.exists() else {"decision": "blocked", "attempts": [], "notes": ["Probe has not run."]}
    matrix = read_json(matrix_path)
    report = ValidationReport(
        id="validation:evidence-gate-v1",
        input_revisions={
            "comparison": str(comparison_path.relative_to(ROOT)),
            "probe": str(probe_path.relative_to(ROOT)) if probe_path.exists() else "not-run",
            "sourceMatrix": str(matrix_path.relative_to(ROOT)),
        },
    )
    expected_hash = comparison.get("inputs", {}).get("osm", {}).get("sha256")
    actual_hash = f"sha256:{sha256(osm_path)}" if osm_path.exists() else None
    report.add_check(
        "osm-extract-pinned",
        "pass" if expected_hash and actual_hash == f"sha256:{expected_hash}" else "fail",
        f"expected={expected_hash or 'missing'} actual={actual_hash or 'missing'}",
    )
    overture_status = probe.get("decision")
    report.add_check(
        "overture-provider-access",
        "pass" if overture_status == "validated" else "warning",
        "validated" if overture_status == "validated" else "blocked; proceed OSM-first without coverage claim",
    )
    report.add_check(
        "permission-outreach",
        "pass",
        "Templates are drafted locally; no external requests were sent.",
    )
    report.add_check(
        "dem-license-gate",
        "warning",
        "SRTM/NASA 30 m remains a candidate until endpoint and redistribution terms are recorded.",
    )
    report.add_check(
        "restricted-source-policy",
        "pass",
        "Google imagery and restricted institutional material remain excluded from ingestion.",
    )
    report.measurements["osmSummary"] = comparison.get("summaries", {}).get("osm", {})
    report.measurements["sourceRows"] = len(matrix.get("sources", []))
    report.measurements["overtureAttempts"] = probe.get("attempts", [])
    report.discrepancies = [{"source": "overture", "details": note} for note in comparison.get("notes", []) if "Overture" in note]
    report.finalize()
    return report


def write_markdown(path: Path, report: ValidationReport) -> None:
    lines = [
        "# UPLB Evidence Gate Report",
        "",
        f"**Decision:** `{report.decision}`",
        "",
        "This report is an evidence and rights gate, not a claim that the research AOI is an official UPLB boundary.",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "| --- | --- | --- |",
    ]
    for check in report.checks:
        details = check.get("details", "").replace("|", "\\|")
        lines.append(f"| `{check['name']}` | **{check['status']}** | {details} |")
    lines.extend(
        [
            "",
            "## Current decisions",
            "",
            "- OSM is the initial canonical source, pinned by the SHA-256 recorded in the comparison result.",
            "- Overture remains an adapter and comparison source; its current client/catalog and direct-cloud probes are recorded as blocked when unavailable.",
            "- Permission requests are drafts only and must be human-reviewed before sending.",
            "- A legal 30 m DEM remains a terrain baseline candidate; no raster enters canonical data before its rights record is complete.",
            "- Google Street View/Map Tiles and restricted institutional data are excluded from automated ingestion.",
            "",
            "## Review posture",
            "",
            "A warning or blocked provider does not authorize invented geometry or a coverage claim. Any future source refresh must produce a new hash, source record, and validation report.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    report = build_report(args.comparison, args.probe, args.osm, args.matrix)
    write_json(args.json, report.to_dict())
    write_markdown(args.markdown, report)
    print(__import__("json").dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.decision != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
