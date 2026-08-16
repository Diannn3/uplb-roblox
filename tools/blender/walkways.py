from __future__ import annotations

from typing import Any

from .config import GreyboxConfig


def resolve_walkway_width(properties: dict[str, Any], config: GreyboxConfig) -> tuple[float, str, str]:
    attributes = properties.get("attributes") or {}
    tags = attributes.get("osmTags") or {}
    try:
        width = float(attributes.get("width") or tags.get("width"))
        if width > 0:
            return width, "explicit-source-width", "source-supported"
    except (TypeError, ValueError):
        pass
    return config.default_walkway_width_m, "conservative-walkway-fallback-width", "approximate"
