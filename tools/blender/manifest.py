from __future__ import annotations

import hashlib
import json
from typing import Any


def input_hash(feature: dict[str, Any]) -> str:
    encoded = json.dumps(feature, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def object_id(properties: dict[str, Any]) -> str:
    prefix = {"hero": "HERO", "context-building": "BLDG", "road": "ROAD", "walkway": "PATH", "water": "WATER", "green-space": "GREEN", "landmark-placeholder": "LANDMARK"}.get(str(properties.get("worldgenRole")), "CTX")
    safe = "".join(character if character.isalnum() else "_" for character in str(properties.get("featureId") or properties.get("candidateId"))).strip("_")
    return f"{prefix}__{safe}"
