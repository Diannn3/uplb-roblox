from __future__ import annotations

from pathlib import Path

from tools.modeling.freshness import compare_tree, regenerate_and_compare


def test_compare_tree_detects_changed_generated_artifact(tmp_path) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir(); actual.mkdir()
    (expected / "a.json").write_text('{"v":1}\n', encoding="utf-8")
    (actual / "a.json").write_text('{"v":2}\n', encoding="utf-8")
    report = compare_tree(expected, actual)
    assert report["status"] == "fail"
    assert report["changed"] == ["a.json"]


def test_regenerate_and_compare_passes_for_same_generator(tmp_path) -> None:
    committed = tmp_path / "committed"
    committed.mkdir()
    (committed / "x.obj").write_text("v 0 0 0\n", encoding="utf-8")

    def generator(root: Path):
        (root / "x.obj").write_text("v 0 0 0\n", encoding="utf-8")

    assert regenerate_and_compare(committed, generator)["status"] == "pass"
