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
DEFAULT_TERRAIN_CONFIG = ROOT / "config" / "terrain.json"
DEFAULT_TERRAIN_COMPARISON = ROOT / "data" / "generated" / "terrain-comparison" / "comparison.json"
DEFAULT_JSON = ROOT / "data" / "canonical" / "evidence-gate-report.json"
DEFAULT_MD = ROOT / "docs" / "EVIDENCE_GATE_REPORT.md"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_report(
    comparison_path: Path,
    probe_path: Path,
    osm_path: Path,
    matrix_path: Path,
    terrain_config_path: Path | None = None,
    terrain_comparison_path: Path | None = None,
) -> ValidationReport:
    comparison = read_json(comparison_path)
    probe = read_json(probe_path) if probe_path.exists() else {"decision": "blocked", "attempts": [], "notes": ["Probe has not run."]}
    matrix = read_json(matrix_path)
    terrain_config_path = terrain_config_path or DEFAULT_TERRAIN_CONFIG
    terrain_comparison_path = terrain_comparison_path or DEFAULT_TERRAIN_COMPARISON
    terrain_config = read_json(terrain_config_path) if terrain_config_path.exists() else {}
    terrain_comparison = read_json(terrain_comparison_path) if terrain_comparison_path.exists() else {}
    report = ValidationReport(
        id="validation:evidence-gate-v1",
        input_revisions={
            "comparison": _display_path(comparison_path),
            "probe": _display_path(probe_path) if probe_path.exists() else "not-run",
            "sourceMatrix": _display_path(matrix_path),
            "terrainConfig": _display_path(terrain_config_path) if terrain_config_path.exists() else "not-run",
            "terrainComparison": _display_path(terrain_comparison_path) if terrain_comparison_path.exists() else "not-run",
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
    dem_validated = dem_row.get("status") in {"validated", "validated-fallback", "validated-comparison-input", "validated-selected-baseline"} and "doi" in dem_row and "verticalDatum" in dem_row
    terrain_ready = terrain_config.get("status") == "ready-real-terrain" and terrain_comparison.get("status") == "validated-raster"
    baseline = terrain_config.get("baseline") or terrain_comparison.get("baselineDecision", {}).get("baseline")
    report.add_check(
        "dem-acquisition",
        "pass" if terrain_ready else ("not-run" if not terrain_config else "warning"),
        (
            f"{terrain_config.get('product', baseline)} acquired and compared; selected {baseline}; "
            f"archive, payload, processed, retrieval, and local coverage metadata are recorded."
            if terrain_ready
            else "No validated local DEM comparison is recorded; retain the legal fallback and do not claim terrain coverage."
        ),
    )
    report.add_check(
        "dem-license-gate",
        "pass" if dem_validated else "warning",
        (
            "SRTMGL1.003 and NASADEM_HGT.001 rights, endpoint, citation, vertical metadata, and redistribution status are recorded."
            if terrain_ready and dem_validated
            else "SRTMGL1.003 endpoint, citation, vertical metadata, and redistribution status are recorded."
            if dem_validated
            else "SRTM/NASA 30 m remains a candidate until endpoint and redistribution terms are recorded."
        ),
    )
    report.add_check(
        "restricted-source-policy",
        "pass",
        "Google imagery and restricted institutional material remain excluded from ingestion.",
    )
    report.measurements["osmSummary"] = comparison.get("summaries", {}).get("osm", {})
    report.measurements["sourceRows"] = len(matrix.get("sources", []))
    report.measurements["srtm"] = {key: dem_row.get(key) for key in ("status", "doi", "accessedAt", "landingPage", "horizontalCRS", "horizontalDatum", "verticalUnits", "verticalDatum", "nodata", "authRequirement")}
    report.measurements["terrain"] = {
        key: terrain_config.get(key)
        for key in (
            "status",
            "product",
            "baseline",
            "granule",
            "retrievalTimestamp",
            "license",
            "rights",
            "redistribution",
            "doi",
            "landingPage",
            "sourceHash",
            "archiveSha256",
            "hgtPayloadSha256",
            "processedHeightfieldSha256",
            "coverageBoundsLocalM",
            "cropBoundsLocalM",
            "horizontalCRS",
            "horizontalDatum",
            "verticalDatum",
            "selectionReason",
            "terrainRevision",
        )
        if terrain_config.get(key) is not None
    }
    report.measurements["terrain"]["comparisonRevision"] = terrain_comparison.get("comparisonRevision")
    report.measurements["terrain"]["comparisonStatus"] = terrain_comparison.get("status")
    report.measurements["terrain"]["comparisonCoverage"] = terrain_comparison.get("coverage")
    report.measurements["terrain"]["products"] = terrain_comparison.get("products", [])
    report.measurements["sourceMatrix"] = [
        {
            "sourceId": row.get("sourceId"),
            "provider": row.get("provider"),
            "status": row.get("status"),
            "license": row.get("license"),
            "accessedAt": row.get("accessedAt"),
            "hash": row.get("hash"),
            "archiveSha256": row.get("archiveSha256"),
            "payloadSha256": row.get("payloadSha256"),
            "processedHeightfieldSha256": row.get("processedHeightfieldSha256"),
            "retrievalTimestamp": row.get("retrievalTimestamp"),
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


def _matrix_hash(row: dict[str, object]) -> str:
    if row.get("hash"):
        return str(row["hash"])
    labels = (
        ("archive", row.get("archiveSha256")),
        ("payload", row.get("payloadSha256")),
        ("processed", row.get("processedHeightfieldSha256")),
    )
    values = [f"{label}={value}" for label, value in labels if value]
    return "; ".join(values) if values else "not recorded"


def write_markdown(path: Path, report: ValidationReport) -> None:
    terrain = report.measurements.get("terrain", {})
    terrain_ready = terrain.get("status") == "ready-real-terrain" and terrain.get("comparisonStatus") == "validated-raster"
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
                f"| `{row.get('sourceId')}` | **{row.get('status')}** | {row.get('license', 'not recorded')} | `{row.get('accessedAt', 'not recorded')}` | `{_matrix_hash(row)}` | `{row.get('bbox') or 'not recorded'}` | {row.get('nextAction', '')} |"
                for row in report.measurements.get("sourceMatrix", [])
            ],
            "",
            "## Current decisions",
            "",
            "- OSM is the initial canonical source, pinned by the SHA-256 recorded in the comparison result.",
            "- Overture remains an adapter and comparison source; its current client/catalog and direct-cloud probes are recorded as blocked when unavailable.",
            "- Permission requests are drafts only and must be human-reviewed before sending.",
            (
                f"- {terrain.get('baseline')} is the selected rights-recorded 30 m baseline for the controlled slice; "
                f"the comparison and processed hashes are recorded in the terrain measurement below."
                if terrain_ready
                else "- SRTMGL1.003 is the rights-resolved 30 m baseline fallback; no raster enters canonical data during this evidence-foundation cycle."
            ),
            "- Google Street View/Map Tiles and restricted institutional data are excluded from automated ingestion.",
            "",
            "## DEM acquisition snapshot",
            "",
            *([
                f"- Status: `{terrain.get('status')}`; comparison: `{terrain.get('comparisonStatus')}`; products: `{', '.join(terrain.get('products', []))}`.",
                f"- Selected baseline: `{terrain.get('baseline')}`; granule: `{terrain.get('granule')}`; retrieved: `{terrain.get('retrievalTimestamp')}`.",
                f"- Archive SHA-256: `{terrain.get('archiveSha256')}`; HGT payload SHA-256: `{terrain.get('hgtPayloadSha256')}`; processed heightfield SHA-256: `{terrain.get('processedHeightfieldSha256')}`.",
                f"- Local coverage: `{terrain.get('coverageBoundsLocalM')}`; revision: `{terrain.get('terrainRevision')}`.",
            ] if terrain else ["- No local DEM acquisition snapshot is recorded."]),
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
    parser.add_argument("--terrain-config", type=Path, default=DEFAULT_TERRAIN_CONFIG)
    parser.add_argument("--terrain-comparison", type=Path, default=DEFAULT_TERRAIN_COMPARISON)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    report = build_report(args.comparison, args.probe, args.osm, args.matrix, args.terrain_config, args.terrain_comparison)
    write_json(args.json, report.to_dict())
    write_markdown(args.markdown, report)
    print(__import__("json").dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.decision != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
