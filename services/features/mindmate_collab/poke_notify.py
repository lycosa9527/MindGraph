"""
Deliver MindMate collab poke notifications via workshop chat WebSocket.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from services.features.mindmate_notify_ws_manager import mindmate_notify_ws_manager
from services.features.workshop_chat_ws_manager import chat_ws_manager


async def send_mindmate_collab_poke(
    *,
    target_user_id: int,
    from_user_id: int,
    from_name: str,
    session_id: str,
    room_code: str,
    room_title: str,
    visibility: str,
) -> bool:
    """Push a poke toast payload to an online user."""
    payload: Dict[str, Any] = {
        "type": "mindmate_collab_poke",
        "from_user_id": from_user_id,
        "from_name": from_name,
        "session_id": session_id,
        "room_code": room_code,
        "room_title": room_title,
        "visibility": visibility,
    }
    delivered = await mindmate_notify_ws_manager.send_to_user(target_user_id, payload)
    if delivered:
        return True
    return await chat_ws_manager.send_to_user(target_user_id, payload)
