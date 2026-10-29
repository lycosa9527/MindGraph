"""
Share a saved canvas diagram into a live seminar.

The chat line carries a library id. Members open their own copy from that line.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import select

from models.domain.auth import User
from models.domain.mindmate_seminar import MindmateSeminarMessage, MindmateSeminarSession
from services.features.mindmate_seminar.group_members import user_is_accepted_member
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from services.features.mindmate_seminar.seminar_message import send_seminar_message
from services.features.mindmate_seminar.visibility import user_may_join_mindmate_seminar
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import actor_rls_session, system_rls_session

logger = logging.getLogger(__name__)

SHARE_NOT_FOUND = "not_found"
SHARE_FORBIDDEN = "forbidden"
SHARE_NOT_LIVE = "not_live"

_CANVAS_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def normalize_canvas_diagram_id(raw: str) -> Optional[str]:
    """Return a lowercase library uuid, or None."""
    text = (raw or "").strip().lower()
    if _CANVAS_ID_RE.fullmatch(text):
        return text
    return None


def canvas_share_message(
    *,
    title: str,
    diagram_id: str,
    image_url: str,
    note: str = "",
) -> str:
    """Chat text for a diagram shared from the canvas into a seminar."""
    safe_title = " ".join((title or "Diagram").split())
    safe_title = safe_title.replace("[", "").replace("]", "")
    safe_title = safe_title.replace("(", "").replace(")", "")
    safe_title = safe_title[:80] or "Diagram"
    safe_note = " ".join((note or "").replace("\x00", " ").split())
    safe_note = safe_note.replace("<!--", "").replace("-->", "")[:500]
    lines = [line for line in (safe_note, safe_title) if line]
    url = (image_url or "").strip()
    if url.startswith("https://") or url.startswith("http://") or url.startswith("/api/"):
        lines.append(f"![{safe_title}]({url})")
    lines.append(f"<!-- mg-diagram-id:{diagram_id} -->")
    return "\n".join(lines)


async def user_may_share_canvas(session: MindmateSeminarSession, user: User) -> bool:
    """Host, accepted member, or a colleague who may enter this school seminar."""
    if session.ended_at is not None:
        return False
    user_id = int(user.id)
    if int(session.owner_user_id) == user_id:
        return True
    if await user_is_accepted_member(session.id, user_id):
        return True
    if session.visibility != ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
        return False
    async with actor_rls_session(user) as db:
        return await user_may_join_mindmate_seminar(
            db,
            visibility=session.visibility,
            owner_user_id=int(session.owner_user_id),
            owner_org_id=session.organization_id,
            joiner_id=user_id,
        )


async def user_may_open_shared_canvas(session: MindmateSeminarSession, user: User) -> bool:
    """Host can always reopen. Others can while the seminar is still live."""
    if int(session.owner_user_id) == int(user.id):
        return True
    if session.ended_at is not None:
        return False
    if await user_may_share_canvas(session, user):
        return True
    return await get_mindmate_seminar_manager().is_participant(session.code, int(user.id))


async def session_contains_canvas_diagram(session_id: str, diagram_id: str) -> bool:
    """True when a seminar message references this library diagram."""
    needle = f"%mg-diagram-id:{diagram_id}%"
    try:
        async with system_rls_session() as db:
            found = (
                await db.execute(
                    select(MindmateSeminarMessage.id)
                    .where(
                        MindmateSeminarMessage.session_id == session_id,
                        MindmateSeminarMessage.content.like(needle),
                    )
                    .limit(1),
                )
            ).scalar_one_or_none()
    except DATABASE_ERRORS as exc:
        logger.warning("[CanvasShare] message lookup failed session=%s: %s", session_id, exc)
        return False
    return found is not None


async def canvas_share_sender_id(session_id: str, diagram_id: str) -> Optional[int]:
    """User id of the person who posted this diagram into the seminar."""
    needle = f"%mg-diagram-id:{diagram_id}%"
    try:
        async with system_rls_session() as db:
            sender = (
                await db.execute(
                    select(MindmateSeminarMessage.sender_user_id)
                    .where(
                        MindmateSeminarMessage.session_id == session_id,
                        MindmateSeminarMessage.content.like(needle),
                        MindmateSeminarMessage.sender_user_id.is_not(None),
                    )
                    .order_by(MindmateSeminarMessage.id.asc())
                    .limit(1),
                )
            ).scalar_one_or_none()
    except DATABASE_ERRORS as exc:
        logger.warning("[CanvasShare] sender lookup failed session=%s: %s", session_id, exc)
        return None
    if isinstance(sender, int):
        return sender
    return None


async def post_canvas_diagram_share(
    session_id: str,
    diagram_id: str,
    user: User,
    *,
    image_url: str,
    note: str = "",
) -> tuple[Optional[dict[str, Any]], str]:
    """
    Post the caller's saved diagram into a live seminar.

    Returns ``(payload, error_code)``. ``error_code`` is empty on success.
    """
    cleaned = normalize_canvas_diagram_id(diagram_id)
    if cleaned is None:
        return None, SHARE_NOT_FOUND
    record = await get_diagram_cache().get_diagram(int(user.id), cleaned)
    if not record:
        return None, SHARE_NOT_FOUND
    mgr = get_mindmate_seminar_manager()
    session = await mgr.load_session_by_id(session_id)
    if session is None:
        return None, SHARE_NOT_FOUND
    if not await mgr.session_accepts_chat(session.code):
        return None, SHARE_NOT_LIVE
    if not await user_may_share_canvas(session, user):
        return None, SHARE_FORBIDDEN

    title = str(record.get("title") or "Diagram")
    content = canvas_share_message(
        title=title,
        diagram_id=cleaned,
        image_url=image_url,
        note=note,
    )
    username = getattr(user, "username", None) or getattr(user, "name", None)
    outcome = await send_seminar_message(
        session_id=session.id,
        user_id=int(user.id),
        username=username if isinstance(username, str) else None,
        content=content,
        to_mindmate=False,
        kind="chat",
    )
    if outcome.error or outcome.saved is None:
        if outcome.error == "room_closed":
            return None, SHARE_NOT_LIVE
        if outcome.error in {"forbidden", "observer_readonly"}:
            return None, SHARE_FORBIDDEN
        return None, SHARE_NOT_FOUND
    saved = outcome.saved
    logger.info(
        "[CanvasShare] posted diagram=%s session=%s user=%s",
        cleaned,
        session.id,
        int(user.id),
    )
    return {"message_id": saved.id, "session_id": session.id, "title": title}, ""
