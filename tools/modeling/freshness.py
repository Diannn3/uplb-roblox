from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Callable


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_tree(expected_root: Path, actual_root: Path, *, suffixes: tuple[str, ...] = (".obj", ".json")) -> dict[str, object]:
    expected_root = Path(expected_root)
    actual_root = Path(actual_root)
    expected = {
        path.relative_to(expected_root).as_posix(): sha256(path)
        for path in expected_root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    }
    actual = {
        path.relative_to(actual_root).as_posix(): sha256(path)
        for path in actual_root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    }
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(path for path in set(expected) & set(actual) if expected[path] != actual[path])
    return {
        "status": "pass" if not missing and not extra and not changed else "fail",
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "expectedFileCount": len(expected),
        "actualFileCount": len(actual),
    }


def regenerate_and_compare(
    committed_root: Path,
    generator: Callable[[Path], object],
    *,
    suffixes: tuple[str, ...] = (".obj", ".json"),
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="uplb-modeling-freshness-") as tmp:
        generated_root = Path(tmp)
        generator(generated_root)
        return compare_tree(Path(committed_root), generated_root, suffixes=suffixes)


def write_report(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
