from tools.modeling.pipeline import build_report


def test_pipeline_report_passes_without_external_services() -> None:
    report = build_report(generate_prototypes=False)
    assert report["status"] == "pass"
    assert report["summary"]["buildingCount"] >= 15
    assert report["recoveryActionCount"] > 0
    assert report["nextGate"]
