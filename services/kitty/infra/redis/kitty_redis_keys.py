"""Redis key templates for Kitty WebSocket sessions (collab-style TTL namespace).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

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
    """Kitty live spec key."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:live_spec"


def kitty_scope_owner_key(ws_session_id: str) -> str:
    """Owner id string for atomic detach verification (same slot as sessionmeta)."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:scope_owner"


def kitty_ws_refcount_key(ws_session_id: str) -> str:
    """Kitty ws refcount key."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:ws_refcount"


def kitty_desktop_focus_key(user_id: int) -> str:
    """Per-user hint: library diagram id last open on desktop MindGraph (mobile pairs via GET)."""
    return f"kitty:desktop_focus:{user_id}"


def kitty_desktop_action_queue_key(user_id: int) -> str:
    """FIFO queue for cross-device Kitty actions consumed by authenticated desktop SPA."""
    return f"kitty:desktop_actions:{user_id}"


def kitty_desktop_action_explicit_key(user_id: int) -> str:
    """Set when mobile REST enqueues a desktop action; gates inactive instant LPOP."""
    return f"kitty:desktop_action_explicit:{user_id}"


def kitty_mobile_active_key(user_id: int) -> str:
    """Per-user set of scopes with an active mobile-lane Kitty WebSocket (desktop poll gate)."""
    return f"kitty:mobile_active:{user_id}"


def kitty_desktop_wake_channel(user_id: int) -> str:
    """Redis pub/sub channel: push mobile_active changes to desktop SSE subscribers."""
    return f"kitty:desktop_wake:{user_id}"


def kitty_one_sentence_turns_key(ws_session_id: str) -> str:
    """Append-only turn log for 一句话生成 panel (scoped to diagram library / ephemeral id)."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:one_sentence:turns"


def kitty_one_sentence_meta_key(ws_session_id: str) -> str:
    """Owner + session metadata for one-sentence turn log (same Redis slot as turns)."""
    tag = str(ws_session_id).strip()
    return f"{{{tag}}}kitty:one_sentence:meta"
