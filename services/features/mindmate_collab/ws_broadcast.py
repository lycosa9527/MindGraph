"""
Broadcast helpers for MindMate collab WebSocket clients.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from services.features.mindmate_collab.redis_keys import fanout_room_key, normalize_collab_code
from services.features.mindmate_collab.ws_registry import (
    ACTIVE_CONNECTIONS,
    force_disconnect_local_room,
)
from services.features.workshop_ws_shutdown_constants import (
    ROOM_IDLE_SHUTDOWN_TYPE,
    SESSION_ENDED_SHUTDOWN_TYPE,
)
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.ws_redis_fanout_publish_core import publish_workshop_fanout_async
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

ROOM_IDLE_CLOSE_CODE = 4010
SESSION_ENDED_CLOSE_CODE = 4011


def _envelope(code: str, mode: str, data_str: str, exclude_user_id: Optional[int] = None) -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "v": 1,
        "k": "ws",
        "code": fanout_room_key(normalize_collab_code(code)),
        "mode": mode,
        "d": data_str,
    }
    if exclude_user_id is not None:
        env["ex"] = exclude_user_id
    return env


def _code_from_room_key(room_key: str) -> str:
    if room_key.startswith("mmc:"):
        return room_key[4:]
    return room_key


async def _push_local(room_key: str, data_str: str, exclude_user_id: Optional[int]) -> None:
    handles = ACTIVE_CONNECTIONS.get(room_key)
    if not handles:
        return
    for user_id, handle in list(handles.items()):
        if exclude_user_id is not None and int(user_id) == int(exclude_user_id):
            continue
        send_queue = handle.send_queue
        try:
            send_queue.put_nowait(("text", data_str))
        except asyncio.QueueFull:
            logger.warning("[MindmateCollabWS] send queue full user=%s room=%s", user_id, room_key)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("[MindmateCollabWS] local push failed: %s", exc)


async def _dispatch_local(room_key: str, data_str: str, exclude_user_id: Optional[int]) -> None:
    """Deliver locally; shutdown frames force-close sockets with 4010/4011."""
    try:
        message = json.loads(data_str)
    except json.JSONDecodeError:
        message = None
    if isinstance(message, dict):
        msg_type = message.get("type")
        raw_code = _code_from_room_key(room_key)
        if msg_type == ROOM_IDLE_SHUTDOWN_TYPE:
            await force_disconnect_local_room(
                raw_code,
                close_code=ROOM_IDLE_CLOSE_CODE,
                close_reason="room idle timeout",
            )
            return
        if msg_type == SESSION_ENDED_SHUTDOWN_TYPE:
            await force_disconnect_local_room(
                raw_code,
                close_code=SESSION_ENDED_CLOSE_CODE,
                close_reason="session ended by host",
            )
            return
    await _push_local(room_key, data_str, exclude_user_id)


async def broadcast_to_all(code: str, message: Dict[str, Any]) -> None:
    """Fan-out a JSON frame to every participant in the room."""
    data_str = json.dumps(message, ensure_ascii=False)
    room_key = fanout_room_key(normalize_collab_code(code))
    if is_ws_fanout_enabled():
        try:
            await publish_workshop_fanout_async(_envelope(code, "all", data_str))
        except REDIS_ERRORS as exc:
            logger.warning("[MindmateCollabWS] fanout publish failed: %s", exc)
            await _dispatch_local(room_key, data_str, None)
        return
    await _dispatch_local(room_key, data_str, None)


async def broadcast_to_others(code: str, sender_id: int, message: Dict[str, Any]) -> None:
    """Fan-out a JSON frame to all participants except the sender."""
    data_str = json.dumps(message, ensure_ascii=False)
    room_key = fanout_room_key(normalize_collab_code(code))
    if is_ws_fanout_enabled():
        try:
            await publish_workshop_fanout_async(_envelope(code, "others", data_str, sender_id))
        except REDIS_ERRORS as exc:
            logger.warning("[MindmateCollabWS] fanout publish failed: %s", exc)
            await _dispatch_local(room_key, data_str, sender_id)
        return
    await _dispatch_local(room_key, data_str, sender_id)


async def deliver_fanout_envelope(envelope: Dict[str, Any]) -> None:
    """Deliver a workshop fanout envelope targeted at mmc: room keys."""
    code_key = str(envelope.get("code") or "")
    if not code_key.startswith("mmc:"):
        return
    data_raw = envelope.get("d")
    if not isinstance(data_raw, str):
        return
    exclude = envelope.get("ex")
    exclude_id = int(exclude) if exclude is not None else None
    mode = str(envelope.get("mode") or "all")
    if mode == "others" and exclude_id is not None:
        await _dispatch_local(code_key, data_raw, exclude_id)
    else:
        await _dispatch_local(code_key, data_raw, None)
