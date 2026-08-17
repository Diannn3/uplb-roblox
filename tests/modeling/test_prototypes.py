from pathlib import Path

from tools.modeling.prototypes import generate_baker_massing, generate_kit_prototypes


def test_baker_prototype_writes_obj(tmp_path: Path) -> None:
    result = generate_baker_massing(output_path=tmp_path / "baker.obj")
    assert (tmp_path / "baker.obj").exists()
    assert result["featureId"] == "uplb:building:baker-hall"
    assert result["vertexCount"] > 8
    assert result["triangleEquivalent"] > 10


def test_kit_prototypes_have_unique_ids(tmp_path: Path) -> None:
    result = generate_kit_prototypes(output_dir=tmp_path)
    ids = [row["id"] for row in result]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 5
