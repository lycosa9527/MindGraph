"""Send JSON frames to process-local Kitty WebSockets.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict, FrozenSet, Optional

from fastapi.websockets import WebSocketState

from services.kitty.session.runtime_state import voice_sessions
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


def _session_user_id(sess: Dict[str, Any]) -> Optional[int]:
    raw_uid = sess.get("user_id")
    if raw_uid is None:
        return None
    try:
        return int(raw_uid)
    except (TypeError, ValueError):
        return None


def _session_scope(sess: Dict[str, Any]) -> str:
    return str(sess.get("diagram_session_id") or "").strip()


def _session_lane(sess: Dict[str, Any]) -> str:
    raw = sess.get("_kitty_client_lane")
    return raw.strip() if isinstance(raw, str) and raw.strip() else ""


async def _safe_send(websocket: Any, body: Dict[str, Any]) -> bool:
    try:
        if getattr(websocket, "client_state", None) != WebSocketState.CONNECTED:
            return False
        await websocket.send_json(body)
        return True
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[KittyLaneSend] ws send failed: %s", exc)
        return False


async def send_kitty_ws_json(
    user_id: int,
    body: Dict[str, Any],
    *,
    scope: Optional[str] = None,
    lanes: Optional[FrozenSet[str]] = None,
    exclude_lanes: Optional[FrozenSet[str]] = None,
) -> int:
    """Push ``body`` to matching local Kitty sockets. Returns send count."""
    scope_key = scope.strip() if isinstance(scope, str) and scope.strip() else None
    sent = 0
    seen: set[int] = set()
    for sess in list(voice_sessions.values()):
        if not isinstance(sess, dict):
            continue
        sess_uid = _session_user_id(sess)
        if sess_uid is None or sess_uid != int(user_id):
            continue
        if scope_key is not None and _session_scope(sess) != scope_key:
            continue
        lane = _session_lane(sess)
        if lanes is not None and lane not in lanes:
            continue
        if exclude_lanes is not None and lane in exclude_lanes:
            continue
        websocket = sess.get("_client_websocket")
        if websocket is None:
            continue
        marker = id(websocket)
        if marker in seen:
            continue
        seen.add(marker)
        if await _safe_send(websocket, body):
            sent += 1
    return sent


def iter_local_kitty_scopes(user_id: int) -> list[str]:
    """Unique diagram scopes for this user's local Kitty sockets."""
    found: list[str] = []
    seen: set[str] = set()
    for sess in list(voice_sessions.values()):
        if not isinstance(sess, dict):
            continue
        sess_uid = _session_user_id(sess)
        if sess_uid is None or sess_uid != int(user_id):
            continue
        scope = _session_scope(sess)
        if not scope or scope in seen:
            continue
        seen.add(scope)
        found.append(scope)
    return found
