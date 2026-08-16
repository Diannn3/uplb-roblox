"""Deterministic geospatial foundation for the UPLB Roblox project.

The package deliberately keeps ingestion and validation outside Roblox runtime
code.  Canonical GeoJSON/JSON is the source of truth; generated Luau is a
derived runtime view.
"""

from .models import CanonicalFeature, ConflationReview, ProviderCandidate, SourceRecord, ValidationReport
from .geometry import GeometryState
from .identity import IdentityRegistry
from .transform import CoordinateTransform, ProjectConfig, RobloxPoint

__all__ = [
    "CanonicalFeature",
    "ConflationReview",
    "ProviderCandidate",
    "GeometryState",
    "IdentityRegistry",
    "CoordinateTransform",
    "ProjectConfig",
    "RobloxPoint",
    "SourceRecord",
    "ValidationReport",
]
