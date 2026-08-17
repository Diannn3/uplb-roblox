from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.geodata.evidence_gate import build_report


ROOT = Path(__file__).resolve().parents[2]


def test_evidence_gate_preserves_real_dem_acquisition_provenance() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        terrain_config = root / "terrain.json"
        terrain_comparison = root / "comparison.json"
        terrain_config.write_text(
            json.dumps(
                {
                    "status": "ready-real-terrain",
                    "baseline": "NASADEM_HGT.001",
                    "product": "NASADEM_HGT.001",
                    "granule": "NASADEM_HGT_n14e121",
                    "archiveSha256": "sha256:archive",
                    "hgtPayloadSha256": "sha256:payload",
                    "processedHeightfieldSha256": "sha256:processed",
                    "retrievalTimestamp": "2026-08-17T12:39:12+08:00",
                    "horizontalDatum": "WGS84",
                    "verticalDatum": "EGM96",
                }
            ),
            encoding="utf-8",
        )
        terrain_comparison.write_text(
            json.dumps(
                {
                    "status": "validated-raster",
                    "baselineDecision": {
                        "baseline": "NASADEM_HGT.001",
                        "selectionReason": "lower measured discontinuity",
                    },
                    "products": ["SRTMGL1.003", "NASADEM_HGT.001"],
                }
            ),
            encoding="utf-8",
        )

        report = build_report(
            ROOT / "tests" / "fixtures" / "geodata" / "evidence-gate-comparison.json",
            ROOT / "research" / "results" / "overture_fallback_probe.json",
            ROOT / "tests" / "fixtures" / "geodata" / "osm-small.json",
            ROOT / "tests" / "fixtures" / "geodata" / "evidence-gate-source-matrix.json",
            terrain_config_path=terrain_config,
            terrain_comparison_path=terrain_comparison,
        )

        terrain = report.measurements["terrain"]
        assert report.decision == "pass"
        assert next(check for check in report.checks if check["name"] == "dem-acquisition")["status"] == "pass"
        assert terrain["baseline"] == "NASADEM_HGT.001"
        assert terrain["archiveSha256"] == "sha256:archive"
        assert terrain["hgtPayloadSha256"] == "sha256:payload"
        assert terrain["processedHeightfieldSha256"] == "sha256:processed"
        assert terrain["retrievalTimestamp"] == "2026-08-17T12:39:12+08:00"
        nasadem = next(row for row in report.measurements["sourceMatrix"] if row["sourceId"] == "nasadem-30m")
        assert nasadem["processedHeightfieldSha256"].startswith("sha256:")
        assert report.measurements["osmProvenance"]["state"] == "verified-raw"


def test_evidence_gate_accepts_pinned_manifest_when_raw_extract_is_absent() -> None:
    report = build_report(
        ROOT / "research" / "results" / "osm_overture_comparison.json",
        ROOT / "research" / "results" / "overture_fallback_probe.json",
        ROOT / "research" / "raw" / "clean-clone-missing-osm.json",
        ROOT / "data" / "source-matrix.json",
    )

    assert report.measurements["osmProvenance"]["state"] == "verified-pinned-manifest"
    assert next(check for check in report.checks if check["name"] == "osm-extract-pinned")["status"] == "pass"


def test_evidence_gate_fails_when_missing_raw_has_no_pinned_manifest() -> None:
    with tempfile.TemporaryDirectory() as directory:
        matrix = Path(directory) / "matrix.json"
        matrix.write_text(
            json.dumps(
                {
                    "version": 1,
                    "sources": [
                        {
                            "sourceId": "osm",
                            "provider": "OpenStreetMap contributors",
                            "license": "ODbL-1.0",
                            "accessedAt": "2026-08-17",
                            "status": "validated"
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        report = build_report(
            ROOT / "tests" / "fixtures" / "geodata" / "evidence-gate-comparison.json",
            ROOT / "research" / "results" / "overture_fallback_probe.json",
            Path(directory) / "missing-osm.json",
            matrix,
        )

        assert report.decision == "fail"
        assert report.measurements["osmProvenance"]["state"] == "missing-unverifiable"
        assert next(check for check in report.checks if check["name"] == "osm-extract-pinned")["status"] == "fail"
