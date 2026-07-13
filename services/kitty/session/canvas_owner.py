"""Resolve desktop canvas-owner Kitty WebSocket for verified diagram apply.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import WebSocket

from services.kitty.infra.desktop.kitty_canvas_owner_presence import (
    has_kitty_canvas_owner_present,
)
from services.kitty.session.runtime_state import voice_sessions


def is_canvas_owner_session(session: dict[str, Any]) -> bool:
    """True when the voice session is the desktop canvas apply/ack owner."""
    if session.get("_kitty_canvas_owner") is True:
        return True
    lane = session.get("_kitty_client_lane")
    return lane != "mobile"


def find_canvas_owner_websocket(
    user_id: int,
    diagram_scope: str,
) -> Optional[WebSocket]:
    """
    Return the desktop canvas-owner WebSocket for ``user_id`` + ``diagram_scope``.

    Mobile ingress sessions are never returned — they are mic+chat only.
    """
    scope = str(diagram_scope or "").strip()
    if not scope:
        return None
    for _sid, sess in list(voice_sessions.items()):
        if not isinstance(sess, dict):
            continue
        if str(sess.get("diagram_session_id") or "").strip() != scope:
            continue
        raw_uid = sess.get("user_id")
        if raw_uid is None:
            continue
        try:
            sess_uid = int(raw_uid)
        except (TypeError, ValueError):
            continue
        if sess_uid != int(user_id):
            continue
        if not is_canvas_owner_session(sess):
            continue
        ws = sess.get("_client_websocket")
        if ws is None:
            continue
        return ws
    return None


async def canvas_owner_available(user_id: int, diagram_scope: str) -> bool:
    """
    True when a desktop canvas owner is reachable for apply/ack.

    Checks process-local owner WS first, then Redis presence (cross-worker).
    """
    scope = str(diagram_scope or "").strip()
    if not scope:
        return False
    if find_canvas_owner_websocket(user_id, scope) is not None:
        return True
    return await has_kitty_canvas_owner_present(user_id, scope)


def agent_session_id_for_scope(diagram_session_id: str, *, client_lane: str | None) -> str:
    """Lane-suffixed agent id so mobile + desktop can coexist on one diagram scope."""
    scope = str(diagram_session_id or "").strip()
    if client_lane == "mobile":
        return f"diagram_{scope}:mobile"
    return f"diagram_{scope}"
