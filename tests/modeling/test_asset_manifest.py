from pathlib import Path

from tools.modeling.asset_manifest import build_prototype_asset_manifest
from tools.modeling.prototypes import generate_baker_massing, generate_kit_prototypes


def test_prototype_manifest_records_hashes(tmp_path: Path) -> None:
    # The repository-level integration test below exercises the actual paths.
    # Here we only ensure generated project artifacts are present before reading.
    generate_baker_massing()
    generate_kit_prototypes()
    manifest = build_prototype_asset_manifest()
    assert manifest["status"] == "prototype-only"
    assert any(row["id"] == "asset:prototype:baker-hall-massing" for row in manifest["records"])
    assert all(str(row["sha256"]).startswith("sha256:") for row in manifest["records"])
    assert all(row["productionDisposition"] == "NON_PRODUCTION_REFERENCE" for row in manifest["records"])
