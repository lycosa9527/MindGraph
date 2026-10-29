"""
Deliver MindMate collab poke notifications via workshop chat WebSocket.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from models.domain.mindmate_seminar import MindmateSeminarSession
from services.features.mindmate_seminar.group_members import member_is_pending, seminar_host_org_label
from services.features.mindmate_notify_ws_manager import mindmate_notify_ws_manager
from services.features.workshop_chat_ws_manager import chat_ws_manager


async def send_mindmate_seminar_poke(
    *,
    target_user_id: int,
    from_user_id: int,
    from_name: str,
    session_id: str,
    room_code: str,
    room_title: str,
    visibility: str,
    needs_consent: bool = False,
    brief_topic: str = "",
    host_org: str = "",
) -> bool:
    """Push a poke toast payload to an online user."""
    payload: Dict[str, Any] = {
        "type": "mindmate_seminar_poke",
        "from_user_id": from_user_id,
        "from_name": from_name,
        "session_id": session_id,
        "room_code": room_code,
        "room_title": room_title,
        "visibility": visibility,
        "needs_consent": needs_consent,
        "brief_topic": brief_topic,
        "host_org": host_org,
    }
    delivered = await mindmate_notify_ws_manager.send_to_user(target_user_id, payload)
    if delivered:
        return True
    return await chat_ws_manager.send_to_user(target_user_id, payload)


async def send_seminar_member_poke(
    *,
    session: MindmateSeminarSession,
    target_user_id: int,
    from_user_id: int,
    from_name: str,
) -> bool:
    """Nudge a member. Cross-school invites carry the seminar basics for consent."""
    pending = await member_is_pending(session.id, target_user_id)
    host_org = await seminar_host_org_label(session.organization_id) if pending else ""
    return await send_mindmate_seminar_poke(
        target_user_id=target_user_id,
        from_user_id=from_user_id,
        from_name=from_name,
        session_id=session.id,
        room_code=session.code,
        room_title=session.title or "MindMate Collab",
        visibility=session.visibility,
        needs_consent=pending,
        brief_topic=(session.brief_topic or "").strip() if pending else "",
        host_org=host_org,
    )
