from __future__ import annotations

from typing import Any

from .config import GreyboxConfig


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_height(properties: dict[str, Any], config: GreyboxConfig) -> tuple[float, str, str]:
    attributes = properties.get("attributes") or {}
    osm_tags = attributes.get("osmTags") or {}
    verification = properties.get("verification") or {}
    explicit = _number(attributes.get("height") or osm_tags.get("height"))
    if explicit is not None and explicit > 0 and verification.get("height") in {"human-reviewed", "verified"}:
        return explicit, "human-verified-explicit-height", "human-reviewed"
    provider = _number(attributes.get("providerHeight") or osm_tags.get("building:height"))
    if provider is not None and provider > 0:
        return provider, "reliable-provider-height", "source-supported"
    levels = _number(attributes.get("levels") or osm_tags.get("building:levels"))
    if levels is not None and levels > 0:
        if verification.get("height") in {"human-reviewed", "verified"}:
            return levels * config.default_floor_height_m, "human-reviewed-floor-count-x-default-floor-height", "approximate"
        return levels * config.default_floor_height_m, "source-supported-floor-count-x-default-floor-height", "approximate"
    return config.default_building_height_m, "conservative-feature-placeholder", "placeholder"
