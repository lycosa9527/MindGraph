"""Workshop WebSocket broadcast helpers (fan-out vs in-memory)."""

import json
import logging
from typing import Any, Dict

from fastapi.websockets import WebSocketState

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.ws_redis_fanout_publish import publish_workshop_fanout_async
from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
)
from services.workshop.workshop_service import workshop_service

logger = logging.getLogger(__name__)


async def broadcast_to_others(code: str, sender_id: int, message: Dict[str, Any]) -> None:
    """Broadcast message to all participants except sender."""
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(message, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] broadcast_to_others: serialize failed")
            return
        await publish_workshop_fanout_async(
            {
                "v": 1,
                "k": "ws",
                "code": code,
                "mode": "others",
                "ex": sender_id,
                "d": data_str,
            }
        )
        return

    if code not in active_connections:
        return

    disconnected = []
    for user_id, websocket in active_connections[code].items():
        if user_id == sender_id:
            continue

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
            else:
                disconnected.append(user_id)
        except Exception as exc:
            logger.warning(
                "[WorkshopWS] Error broadcasting to user %s: %s",
                user_id,
                exc,
            )
            disconnected.append(user_id)

    for user_id in disconnected:
        active_connections[code].pop(user_id, None)
        await workshop_service.remove_participant(code, user_id)


async def broadcast_to_all(code: str, message: Dict[str, Any]) -> None:
    """Broadcast message to all participants."""
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(message, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] broadcast_to_all: serialize failed")
            return
        await publish_workshop_fanout_async(
            {
                "v": 1,
                "k": "ws",
                "code": code,
                "mode": "all",
                "ex": None,
                "d": data_str,
            }
        )
        return

    if code not in active_connections:
        return

    disconnected = []
    for user_id, websocket in active_connections[code].items():
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
            else:
                disconnected.append(user_id)
        except Exception as exc:
            logger.warning(
                "[WorkshopWS] Error broadcasting to user %s: %s",
                user_id,
                exc,
            )
            disconnected.append(user_id)

    for user_id in disconnected:
        active_connections[code].pop(user_id, None)
        await workshop_service.remove_participant(code, user_id)
