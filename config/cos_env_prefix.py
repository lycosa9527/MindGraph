"""Per-environment COS app identity (local / test / production)."""

from __future__ import annotations

import os

_PRODUCTION_ALIASES = frozenset({"", "production", "prod"})
_KNOWN_SUFFIX = {
    "test": "Test",
    "development": "Dev",
    "dev": "Dev",
    "staging": "Staging",
}


def cos_app_identity(environment: str | None = None) -> str:
    """Return ``mindgraph`` / ``mindgraph-Test`` / ``mindgraph-Dev`` from ENVIRONMENT."""
    raw = os.getenv("ENVIRONMENT", "production") if environment is None else environment
    key = str(raw).strip().lower()
    if key in _PRODUCTION_ALIASES:
        return "mindgraph"
    suffix = _KNOWN_SUFFIX.get(key)
    if suffix is None:
        token = key.replace("_", "-").strip("-")
        if not token:
            return "mindgraph"
        return f"mindgraph-{token[:1].upper()}{token[1:]}"
    return f"mindgraph-{suffix}"


def cos_feature_prefix(feature: str, override: str | None = None) -> str:
    """Build ``{feature}/{identity}`` unless an explicit prefix override is set."""
    if override is not None:
        stripped = override.strip().rstrip("/")
        if stripped:
            return stripped
    name = feature.strip().strip("/")
    if not name:
        raise ValueError("COS feature name required")
    return f"{name}/{cos_app_identity()}"
