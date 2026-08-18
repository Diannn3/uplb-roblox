from __future__ import annotations

from tools.modeling.hashing import semantic_json_sha256


def test_semantic_json_hash_ignores_newline_style_and_whitespace(tmp_path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    compact = tmp_path / "compact.json"
    lf.write_bytes(b'{\n  "a": 1,\n  "b": [2, 3]\n}\n')
    crlf.write_bytes(b'{\r\n  "a": 1,\r\n  "b": [2, 3]\r\n}\r\n')
    compact.write_bytes(b'{"b":[2,3],"a":1}')
    assert semantic_json_sha256(lf) == semantic_json_sha256(crlf)
    assert semantic_json_sha256(lf) == semantic_json_sha256(compact)
