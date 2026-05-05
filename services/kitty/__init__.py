"""Kitty agent session support (Redis-backed live context, collab-style).

See ``README.md`` in this package for production workflow (scopes, handoff, Redis).
"""

from services.kitty.kitty_ws_scope import normalize_kitty_diagram_session_id

__all__ = ["normalize_kitty_diagram_session_id"]
