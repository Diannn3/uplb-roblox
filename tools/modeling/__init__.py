"""Campus-scale modeling production tooling for the UPLB Roblox project.

The package intentionally treats 3D assets as derived products. Canonical identity,
source evidence, production specs, and stable asset manifests stay in Git.
"""

from .registry import ModelingRegistry, load_registry

__all__ = ["ModelingRegistry", "load_registry"]
