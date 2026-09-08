"""Shared COS folder layout: ``{env}/{module}/...``.

``ENVIRONMENT`` maps to one root folder so every feature shares it:

* development / dev → ``dev``
* test → ``test``
* production / prod → live ``{module}/mindgraph`` until ``COS_ENV_PREFIX=production``
* staging → ``staging``

Set ``COS_ENV_PREFIX`` to override the root (smoke, or ``production`` after migrate).
Per-module ``COS_*_PREFIX`` overrides remain for legacy buckets.
``COS_SYNC_KEY_PREFIX`` stays outside this tree (shared across hosts).
"""

from __future__ import annotations

import os

_PRODUCTION_ALIASES = frozenset({"", "production", "prod"})
_ENV_ROOT = {
    "": "production",
    "production": "production",
    "prod": "production",
    "test": "test",
    "development": "dev",
    "dev": "dev",
    "staging": "staging",
}
_KNOWN_SUFFIX = {
    "test": "Test",
    "development": "Dev",
    "dev": "Dev",
    "staging": "Staging",
}


def _environment_key(environment: str | None) -> str:
    if environment is None:
        raw = os.getenv("ENVIRONMENT", "production")
    else:
        raw = environment
    return str(raw).strip().lower()


def cos_env_root(environment: str | None = None) -> str:
    """Return ``dev`` / ``test`` / ``production`` (or ``COS_ENV_PREFIX``)."""
    if environment is None:
        override = os.getenv("COS_ENV_PREFIX", "").strip().strip("/")
        if override:
            return override
    key = _environment_key(environment)
    mapped = _ENV_ROOT.get(key)
    if mapped:
        return mapped
    token = key.replace("_", "-").strip("-")
    return token or "production"


def cos_app_identity(environment: str | None = None) -> str:
    """Legacy module-first identity: ``mindgraph`` / ``mindgraph-Test`` / ``mindgraph-Dev``."""
    key = _environment_key(environment)
    if key in _PRODUCTION_ALIASES:
        return "mindgraph"
    suffix = _KNOWN_SUFFIX.get(key)
    if suffix is None:
        token = key.replace("_", "-").strip("-")
        if not token:
            return "mindgraph"
        return f"mindgraph-{token[:1].upper()}{token[1:]}"
    return f"mindgraph-{suffix}"


def cos_production_tree_enabled() -> bool:
    """True only when operators set ``COS_ENV_PREFIX=production``."""
    return os.getenv("COS_ENV_PREFIX", "").strip().strip("/") == "production"


def uses_live_production_prefixes() -> bool:
    """Production host that has not opted into the new ``production/`` tree."""
    if os.getenv("COS_ENV_PREFIX", "").strip():
        return False
    return cos_env_root() == "production"


def cos_feature_prefix(feature: str, override: str | None = None) -> str:
    """Build ``{env}/{feature}`` unless an explicit prefix override is set.

    ``ENVIRONMENT=production`` without ``COS_ENV_PREFIX=production`` keeps the
    live ``{module}/mindgraph`` keys. The new ``production/`` tree is opt-in.
    """
    if override is not None:
        stripped = override.strip().rstrip("/")
        if stripped:
            return stripped
    name = feature.strip().strip("/")
    if not name:
        raise ValueError("COS feature name required")
    if uses_live_production_prefixes():
        return f"{name}/mindgraph"
    return f"{cos_env_root()}/{name}"
