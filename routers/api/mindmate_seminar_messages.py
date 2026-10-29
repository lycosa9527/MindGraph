"""Seminar transcript: save a line and read pages of saved lines.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from models.domain.auth import User
from models.domain.messages import Language
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from services.features.mindmate_seminar.config import MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from services.features.mindmate_seminar.seminar_message import (
    SEMINAR_MESSAGE_KIND_CHAT,
    send_seminar_message,
)
from utils.auth import get_current_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter()

_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "observer_readonly": status.HTTP_403_FORBIDDEN,
    "room_closed": status.HTTP_409_CONFLICT,
    "content_too_long": status.HTTP_400_BAD_REQUEST,
    "invalid_payload": status.HTTP_400_BAD_REQUEST,
}


class SendSeminarMessageBody(BaseModel):
    """One seminar line. Minutes keep the ``[[seminar-summary]]`` marker in ``content``."""

    content: str = Field(min_length=1, max_length=MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS)
    to_mindmate: bool = False
    kind: Literal["chat", "minutes"] = SEMINAR_MESSAGE_KIND_CHAT


async def _require_collab_tier(current_user: User, lang: Language) -> None:
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_ONLINE_COLLAB,
            lang,
        )


def _display_name(user: User) -> Optional[str]:
    username = getattr(user, "username", None) or getattr(user, "name", None)
    if isinstance(username, str) and username.strip():
        return username.strip()
    return None


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def create_seminar_message(
    session_id: str,
    body: SendSeminarMessageBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Save a seminar line. Open sockets receive the saved row; the socket is not the writer."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_send_message",
        get_rate_limit_identifier(current_user, request),
        max_requests=60,
        window_seconds=60,
    )
    outcome = await send_seminar_message(
        session_id=session_id,
        user_id=int(current_user.id),
        username=_display_name(current_user),
        content=body.content,
        to_mindmate=body.to_mindmate,
        kind=body.kind,
    )
    if outcome.error or outcome.saved is None:
        code = outcome.error or "invalid_payload"
        raise HTTPException(status_code=_STATUS.get(code, status.HTTP_400_BAD_REQUEST), detail=code)
    saved = outcome.saved
    payload = {
        "id": saved.id,
        "prev_id": saved.prev_id,
        "created_at": saved.created_at,
        "content": body.content.strip(),
        "role": outcome.role,
        "sender_user_id": None if outcome.role == "assistant" else int(current_user.id),
        "kind": body.kind,
        "to_mindmate": body.to_mindmate if body.kind == SEMINAR_MESSAGE_KIND_CHAT else False,
    }
    if outcome.warning:
        payload["warning"] = outcome.warning
    return payload


@router.get("/{session_id}/messages")
async def list_seminar_messages(
    request: Request,
    session_id: str,
    limit: int = Query(100, ge=1, le=200),
    after_id: Optional[int] = Query(None, ge=0),
    before_id: Optional[int] = Query(None, ge=0),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """One page of seminar lines. ``after_id`` is newer; ``before_id`` is older."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_seminar_history",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    if after_id is not None and before_id is not None:
        raise HTTPException(status_code=400, detail="Choose after_id or before_id")
    manager = get_mindmate_seminar_manager()
    session = await manager.load_session_by_id_any(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Room not found")
    if not await manager.user_may_connect(current_user.id, session):
        raise HTTPException(status_code=403, detail="Access denied")
    page = await manager.fetch_message_page(
        session_id,
        limit=limit,
        after_id=after_id,
        before_id=before_id,
    )
    return {"messages": page.messages, "has_more": page.has_more}
