from __future__ import annotations

from typing import Any


def environment_dimensions(properties: dict[str, Any]) -> tuple[float, str]:
    feature_type = str(properties.get("featureType", ""))
    if feature_type in {"water", "waterway"}:
        return 2.0, "water-placeholder-width"
    return 1.0, "green-space-placeholder"
