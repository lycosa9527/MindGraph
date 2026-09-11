"""
Optional ``Origin`` allowlist for canvas-collab WebSocket upgrades.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Any, FrozenSet

from starlette.datastructures import Headers

logger = logging.getLogger(__name__)


def normalize_origin_header(origin: str) -> str:
    """Lowercase scheme and host portion for comparisons."""
    trimmed = origin.strip()
    if not trimmed:
        return ""
    lowered = trimmed.lower()
    if lowered.endswith("/"):
        return lowered[:-1]
    return lowered


def parse_collab_ws_allowed_origins(raw: str | None) -> FrozenSet[str]:
    """
    Parse ``COLLAB_WS_ALLOWED_ORIGINS`` (comma-separated full origins).

    Example: ``https://app.example.com,https://staging.example.com``
    Empty or unset env → enforcement disabled (backward compatible).
    """
    if not raw:
        return frozenset()
    parts = []
    for piece in raw.split(","):
        norm = normalize_origin_header(piece)
        if norm:
            parts.append(norm)
    return frozenset(parts)


def first_party_ws_origins_from_env() -> FrozenSet[str]:
    """Public site origin from ``EXTERNAL_BASE_URL`` (Word Voice, ESP32 watch)."""
    return parse_collab_ws_allowed_origins(os.environ.get("EXTERNAL_BASE_URL"))


def load_collab_ws_allowed_origins_env() -> FrozenSet[str]:
    """Load CSWSH allowlist; policy off when ``COLLAB_WS_ALLOWED_ORIGINS`` is empty."""
    configured = parse_collab_ws_allowed_origins(os.environ.get("COLLAB_WS_ALLOWED_ORIGINS"))
    if not configured:
        return frozenset()
    return frozenset(configured | first_party_ws_origins_from_env())


def canvas_collab_websocket_origin_is_allowed(
    headers: Headers,
    allowed_normalized: FrozenSet[str],
) -> bool:
    """
    Returns whether the upgrade ``Origin`` is permitted.

    When ``allowed_normalized`` is empty, returns True (policy off).
    When policy is active, browsers send ``Origin``; missing header fails.
    The public site (``EXTERNAL_BASE_URL``) is also first-party — same host as
    the Word Voice dialog and the watch's configured server URL.
    Native / test clients without ``Origin`` can set
    ``COLLAB_WS_ALLOW_MISSING_ORIGIN=1`` to permit empty header when policy is on.
    """
    if not allowed_normalized:
        return True

    missing_ok = os.environ.get("COLLAB_WS_ALLOW_MISSING_ORIGIN", "0").lower() in ("1", "true", "yes")

    raw = headers.get("origin")
    if not raw or not raw.strip():
        return bool(missing_ok)

    cand = normalize_origin_header(raw)
    permitted = frozenset(allowed_normalized | first_party_ws_origins_from_env())
    return cand in permitted


async def close_ws_if_origin_disallowed(websocket: Any, context: str) -> bool:
    """Close the WebSocket and return True when its ``Origin`` is not allowed.

    Shares the ``COLLAB_WS_ALLOWED_ORIGINS`` allowlist so every
    cookie-authenticated WS endpoint (collab, ASR, translate, chat) enforces
    one CSWSH policy. Returns False (allowed) when policy is off or the Origin
    matches. The caller must stop processing when this returns True.
    """
    allowed = load_collab_ws_allowed_origins_env()
    if canvas_collab_websocket_origin_is_allowed(websocket.headers, allowed):
        return False
    logger.warning(
        "[%s] WebSocket origin rejected (CSWSH guard) origin=%s",
        context,
        websocket.headers.get("origin"),
    )
    try:
        await websocket.close(code=1008, reason="Cross-origin connection is not allowed")
    except (RuntimeError, OSError, ConnectionError) as exc:
        logger.debug("[%s] origin-reject close failed: %s", context, exc)
    return True
