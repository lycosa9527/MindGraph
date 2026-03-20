"""
Local WebSocket delivery for diagram workshop Redis fan-out (per worker).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi.websockets import WebSocketState

from services.features.workshop_ws_connection_state import ACTIVE_CONNECTIONS
from services.workshop import workshop_service

logger = logging.getLogger(__name__)


async def deliver_local_workshop_broadcast(
    code: str,
    mode: str,
    exclude_user: Optional[int],
    data_str: str,
) -> None:
    """Deliver a workshop payload to WebSockets connected on this worker."""
    try:
        message = json.loads(data_str)
    except json.JSONDecodeError:
        return
    if code not in ACTIVE_CONNECTIONS:
        return

    disconnected = []
    for user_id, ws_conn in list(ACTIVE_CONNECTIONS[code].items()):
        if mode == "others" and exclude_user is not None and user_id == exclude_user:
            continue
        try:
            if ws_conn.client_state == WebSocketState.CONNECTED:
                await ws_conn.send_json(message)
            else:
                disconnected.append(user_id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "[WorkshopWS] Fan-out deliver to user %s: %s",
                user_id,
                exc,
            )
            disconnected.append(user_id)

    for uid in disconnected:
        ACTIVE_CONNECTIONS[code].pop(uid, None)
        await workshop_service.remove_participant(code, uid)
