"""Redis key templates for Kitty WebSocket sessions (collab-style TTL namespace)."""

import os


def kitty_redis_ttl_seconds() -> int:
    """TTL for kitty:sessionmeta / kitty:live_spec keys (default 4 hours)."""
    raw = os.getenv("KITTY_SESSION_REDIS_TTL_SECONDS", "").strip()
    if raw.isdigit():
        return max(60, int(raw))
    return 4 * 3600


def kitty_refcount_ttl_seconds() -> int:
    """TTL for global WebSocket refcount (default min(session TTL, 1h); heals leaked counters)."""
    raw = os.getenv("KITTY_WS_REFCOUNT_TTL_SECONDS", "").strip()
    if raw.isdigit():
        return max(60, int(raw))
    return min(3600, kitty_redis_ttl_seconds())


def kitty_sessionmeta_key(ws_session_id: str) -> str:
    """Cluster-safe: hash tag uses scope so Lua can touch refcount + meta together."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:sessionmeta"


def kitty_live_spec_key(ws_session_id: str) -> str:
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:live_spec"


def kitty_scope_owner_key(ws_session_id: str) -> str:
    """Owner id string for atomic detach verification (same slot as sessionmeta)."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:scope_owner"


def kitty_ws_refcount_key(ws_session_id: str) -> str:
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:ws_refcount"


def kitty_desktop_focus_key(user_id: int) -> str:
    """Per-user hint: library diagram id last open on desktop MindGraph (mobile pairs via GET)."""
    return f"kitty:desktop_focus:{user_id}"
