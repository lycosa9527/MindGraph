"""Save one seminar line in Postgres, then push it to open sockets.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NamedTuple, Optional

from sqlalchemy import select

from models.domain.auth import User
from models.domain.mindmate_seminar import MindmateSeminarSession
from services.auth.expert_school_binding import bound_org_ids_for_user
from services.features.mindmate_seminar.config import (
    MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS,
    MINDMATE_COLLAB_MAX_LIVE_SECONDS,
)
from services.features.mindmate_seminar.dify_stream import schedule_assistant_reply
from services.features.mindmate_seminar.dify_stream_control import acquire_dify_stream_lock
from services.features.mindmate_seminar.group_members import user_observes_seminar
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from services.features.mindmate_seminar.mention import (
    collab_message_targets_mindmate,
    extract_mindmate_query,
    mention_aliases_from_org,
)
from services.features.mindmate_seminar.message_files import strip_seminar_message_file_tokens
from services.features.mindmate_seminar.message_history import PersistedCollabMessage
from services.features.mindmate_seminar.redis_keys import normalize_collab_code, session_meta_key
from services.features.mindmate_seminar.seminar_ttl import seminar_past_max_live_age
from services.features.mindmate_seminar.ws_broadcast import broadcast_to_all
from services.redis.cache.redis_org_cache import org_cache
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import system_rls_session

SEMINAR_MESSAGE_KIND_CHAT = "chat"
SEMINAR_MESSAGE_KIND_MINUTES = "minutes"
SEMINAR_MINUTES_MARKER = "[[seminar-summary]]"
_MESSAGE_KINDS = frozenset({SEMINAR_MESSAGE_KIND_CHAT, SEMINAR_MESSAGE_KIND_MINUTES})


class SeminarMessageOutcome(NamedTuple):
    """Saved line, or an error code. ``warning`` is set when the line saved but AI did not start."""

    error: Optional[str]
    saved: Optional[PersistedCollabMessage]
    role: str
    warning: Optional[str]


def seminar_room_past_live_cap(session: MindmateSeminarSession, now: Optional[datetime] = None) -> bool:
    """True when this open row is already past the 30-day live window."""
    current = now if now is not None else datetime.now(tz=UTC)
    return seminar_past_max_live_age(session.started_at, current)


def _failed(error: str) -> SeminarMessageOutcome:
    return SeminarMessageOutcome(error, None, "", None)


def _live_expires_at(session: MindmateSeminarSession) -> datetime:
    """Clock stored on the Redis hash. Key TTL is the 30-day cap, not this value."""
    if session.expires_at is not None:
        return session.expires_at
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return started + timedelta(seconds=MINDMATE_COLLAB_MAX_LIVE_SECONDS)


async def ensure_live_seminar_room(session: MindmateSeminarSession) -> bool:
    """Republish Redis when the Postgres row is still live and the room hash is gone."""
    if session.ended_at is not None or seminar_room_past_live_cap(session):
        return False
    redis = get_async_redis()
    if not redis:
        return False
    norm = normalize_collab_code(session.code)
    try:
        if await redis.hexists(session_meta_key(norm), "session_id"):
            return True
    except REDIS_ERRORS:
        return False
    async with system_rls_session() as db:
        owner = (await db.execute(select(User).where(User.id == session.owner_user_id))).scalar_one_or_none()
        if owner is None:
            return False
        owner_name = owner.name or owner.phone or owner.email or str(session.owner_user_id)
        bound_org_ids = await bound_org_ids_for_user(db, owner)
    manager = get_mindmate_seminar_manager()
    return await manager.publish_live_room(
        code=session.code,
        session_id=session.id,
        owner_id=session.owner_user_id,
        owner_name=owner_name,
        org_id=session.organization_id,
        title=session.title,
        visibility=session.visibility,
        expires_at=_live_expires_at(session),
        bound_org_ids=bound_org_ids,
        dify_conversation_id=session.dify_conversation_id,
        started_at=session.started_at,
    )


async def _mention_aliases(session: MindmateSeminarSession) -> tuple[str, ...]:
    org_id = session.organization_id
    if org_id is None:
        return ()
    room_org = await org_cache.get_by_id(int(org_id))
    if room_org is None:
        return ()
    return mention_aliases_from_org(room_org)


async def _start_mindmate(
    session: MindmateSeminarSession,
    content: str,
    sender_user_id: int,
    aliases: tuple[str, ...],
) -> Optional[str]:
    """Start the shared AI reply. Returns a warning code when the room is already answering."""
    code = session.code
    if not await acquire_dify_stream_lock(code):
        return "mindmate_responding"
    manager = get_mindmate_seminar_manager()
    conversation_id = await manager.resolve_dify_conversation_id(
        code,
        fallback=session.dify_conversation_id,
    )
    conversation_server = await manager.resolve_dify_conversation_server(
        code,
        fallback=session.dify_conversation_id,
    )
    schedule_assistant_reply(
        code=code,
        session_id=session.id,
        org_id=session.organization_id,
        user_message=extract_mindmate_query(strip_seminar_message_file_tokens(content), aliases),
        sender_user_id=sender_user_id,
        conversation_id=conversation_id,
        conversation_server=conversation_server,
    )
    return None


async def send_seminar_message(
    *,
    session_id: str,
    user_id: int,
    username: Optional[str],
    content: str,
    to_mindmate: bool,
    kind: str,
) -> SeminarMessageOutcome:
    """Insert one chat or minutes line and broadcast the saved row."""
    text = content.strip()
    if kind not in _MESSAGE_KINDS or not text:
        return _failed("invalid_payload")
    if len(text) > MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS:
        return _failed("content_too_long")
    if kind == SEMINAR_MESSAGE_KIND_MINUTES and (to_mindmate or not text.startswith(SEMINAR_MINUTES_MARKER)):
        return _failed("invalid_payload")

    manager = get_mindmate_seminar_manager()
    session = await manager.load_session_by_id(session_id)
    if session is None:
        return _failed("not_found")
    if not await manager.user_may_connect(user_id, session):
        return _failed("forbidden")
    if await user_observes_seminar(session.id, user_id):
        return _failed("observer_readonly")
    if seminar_room_past_live_cap(session) or await manager.session_is_closing(session.code):
        return _failed("room_closed")
    if not await manager.session_accepts_chat(session.code):
        return _failed("room_closed")

    await ensure_live_seminar_room(session)
    await manager.refresh_participant_ttl(session.code, user_id)
    await manager.touch_activity(session.code)

    role = "assistant" if kind == SEMINAR_MESSAGE_KIND_MINUTES else "user"
    sender_id = None if kind == SEMINAR_MESSAGE_KIND_MINUTES else user_id
    saved = await manager.persist_message(
        session.id,
        role=role,
        content=text,
        sender_user_id=sender_id,
        room_code=session.code,
    )
    if kind == SEMINAR_MESSAGE_KIND_MINUTES:
        await broadcast_to_all(
            session.code,
            {
                "type": "seminar_minutes",
                "id": saved.id,
                "prev_id": saved.prev_id,
                "created_at": saved.created_at,
                "content": text,
            },
        )
        return SeminarMessageOutcome(None, saved, role, None)

    aliases = await _mention_aliases(session)
    asks_mindmate = collab_message_targets_mindmate(to_mindmate, text, aliases)
    await broadcast_to_all(
        session.code,
        {
            "type": "user_message",
            "id": saved.id,
            "prev_id": saved.prev_id,
            "created_at": saved.created_at,
            "content": text,
            "sender_user_id": user_id,
            "username": username,
            "to_mindmate": asks_mindmate,
        },
    )
    warning = None
    if asks_mindmate:
        warning = await _start_mindmate(session, text, user_id, aliases)
    return SeminarMessageOutcome(None, saved, role, warning)
