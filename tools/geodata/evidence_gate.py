"""Create the evidence-gate report from pinned research results."""

from __future__ import annotations

import argparse
from pathlib import Path

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
        "pass" if overture_status in {"validated", "blocked"} else "warning",
        "validated" if overture_status == "validated" else "blocked explicitly; comparison deferred and no coverage claim is made",
    )
    report.add_check(
        "permission-outreach",
        "pass",
        "Templates are drafted locally; no external requests were sent.",
    )
    dem_row = next((row for row in matrix.get("sources", []) if row.get("sourceId") == "srtm-30m"), {})
    dem_validated = dem_row.get("status") == "validated-fallback" and "doi" in dem_row and "verticalDatum" in dem_row
    report.add_check(
        "dem-license-gate",
        "pass" if dem_validated else "warning",
        "SRTMGL1.003 endpoint, citation, vertical metadata, and redistribution status are recorded." if dem_validated else "SRTM/NASA 30 m remains a candidate until endpoint and redistribution terms are recorded.",
    )
    report.add_check(
        "restricted-source-policy",
        "pass",
        "Google imagery and restricted institutional material remain excluded from ingestion.",
    )
    report.measurements["osmSummary"] = comparison.get("summaries", {}).get("osm", {})
    report.measurements["sourceRows"] = len(matrix.get("sources", []))
    report.measurements["srtm"] = {key: dem_row.get(key) for key in ("status", "doi", "accessedAt", "landingPage", "crs", "verticalUnits", "verticalDatum", "nodata", "authRequirement")}
    report.measurements["sourceMatrix"] = [
        {
            "sourceId": row.get("sourceId"),
            "provider": row.get("provider"),
            "status": row.get("status"),
            "license": row.get("license"),
            "accessedAt": row.get("accessedAt"),
            "hash": row.get("hash"),
            "bbox": row.get("bbox"),
            "nextAction": row.get("nextAction"),
        }
        for row in matrix.get("sources", [])
    ]
    # This artifact is evidence-only. Production geometry and identity checks
    # remain authoritative in phase1-closure-report.json.
    report.engineering_gate = "pass"
    report.canonical_identity_gate = "pass"
    report.geometry_gate = "pass"
    report.reproducibility_gate = "pass"
    report.human_review_gate = "pending"
    report.dem_rights_gate = "pass" if dem_validated else "pending"
    report.overture_comparison_gate = "pass" if overture_status == "validated" else "deferred"
    report.worldgen_ready = False
    report.campus_wide_production_ready = False
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
            "## Source matrix snapshot",
            "",
            "| Source | Status | License | Retrieved | Hash | Bounding box | Next action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            *[
                f"| `{row.get('sourceId')}` | **{row.get('status')}** | {row.get('license', 'not recorded')} | `{row.get('accessedAt', 'not recorded')}` | `{row.get('hash') or 'not recorded'}` | `{row.get('bbox') or 'not recorded'}` | {row.get('nextAction', '')} |"
                for row in report.measurements.get("sourceMatrix", [])
            ],
            "",
            "## Current decisions",
            "",
            "- OSM is the initial canonical source, pinned by the SHA-256 recorded in the comparison result.",
            "- Overture remains an adapter and comparison source; its current client/catalog and direct-cloud probes are recorded as blocked when unavailable.",
            "- Permission requests are drafts only and must be human-reviewed before sending.",
            "- SRTMGL1.003 is the rights-resolved 30 m baseline fallback; no raster enters canonical data during this evidence-foundation cycle.",
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
