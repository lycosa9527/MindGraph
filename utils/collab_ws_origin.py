"""Optional ``Origin`` allowlist for canvas-collab WebSocket upgrades."""

from __future__ import annotations

import os
from typing import FrozenSet

from starlette.requests import Headers


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


def load_collab_ws_allowed_origins_env() -> FrozenSet[str]:
    return parse_collab_ws_allowed_origins(os.environ.get("COLLAB_WS_ALLOWED_ORIGINS"))


def canvas_collab_websocket_origin_is_allowed(
        headers: Headers,
        allowed_normalized: FrozenSet[str],
) -> bool:
    """
    Returns whether the upgrade ``Origin`` is permitted.

    When ``allowed_normalized`` is empty, returns True (policy off).
    When policy is active, browsers send ``Origin``; missing header fails.
    Native / test clients without ``Origin`` can set
    ``COLLAB_WS_ALLOW_MISSING_ORIGIN=1`` to permit empty header when policy is on.
    """
    if not allowed_normalized:
        return True

    missing_ok = (
        os.environ.get("COLLAB_WS_ALLOW_MISSING_ORIGIN", "0").lower()
        in ("1", "true", "yes")
    )

    raw = headers.get("origin")
    if not raw or not raw.strip():
        return bool(missing_ok)

    cand = normalize_origin_header(raw)
    return cand in allowed_normalized
