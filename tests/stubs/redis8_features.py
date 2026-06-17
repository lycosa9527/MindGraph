"""Legacy hook: tests use the real ``redis8_features`` module (env flags default off)."""

from __future__ import annotations


def install_redis8_features_stub() -> None:
    """No-op — kept for conftest compatibility after online_collab package layout fix."""
