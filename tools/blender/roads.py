from __future__ import annotations

from typing import Any

from .config import GreyboxConfig


def resolve_width(properties: dict[str, Any], config: GreyboxConfig) -> tuple[float, str, str]:
    attributes = properties.get("attributes") or {}
    tags = attributes.get("osmTags") or {}
    try:
        width = float(attributes.get("width") or tags.get("width"))
        if width > 0:
            return width, "explicit-source-width", "source-supported"
    except (TypeError, ValueError):
        pass
    highway = str(attributes.get("highway") or tags.get("highway") or "")
    defaults = {"motorway": 10.0, "primary": 8.0, "secondary": 7.0, "tertiary": 6.0, "residential": 5.0, "service": 4.0}
    if highway in defaults:
        return defaults[highway], "classification-default-width", "approximate"
    return config.default_road_width_m, "conservative-fallback-width", "placeholder"
