"""Archive a MindMate seminar reply as a Word file in 产物."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabMessage, MindmateCollabSession
from services.features.mindmate_collab.background_files import (
    find_reply_artifact,
    save_generated_background_file,
)
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.ws_broadcast import broadcast_to_all
from services.mindmate.reply_docx import build_archived_reply_docx
from services.mindmate.teaching_design_template_store import DOCX_READ_ERRORS
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_ARCHIVE_ERRORS = (
    *DATABASE_ERRORS,
    *DOCX_READ_ERRORS,
    FileNotFoundError,
    OSError,
    ValueError,
    RuntimeError,
)


async def _assistant_reply(session_id: str, message_id: int) -> tuple[str, str | None]:
    async with system_rls_session() as db:
        message = await db.get(MindmateCollabMessage, message_id)
        if message is None or message.session_id != session_id or message.role != "assistant":
            raise ValueError("message_not_found")
        prompt_result = await db.execute(
            select(MindmateCollabMessage.content)
            .where(
                MindmateCollabMessage.session_id == session_id,
                MindmateCollabMessage.role == "user",
                MindmateCollabMessage.id < message_id,
            )
            .order_by(MindmateCollabMessage.id.desc())
            .limit(1)
        )
        prompt = prompt_result.scalar_one_or_none()
        user_prompt = prompt if isinstance(prompt, str) else None
        return message.content, user_prompt


async def _uploader(user_id: int) -> tuple[int | None, str | None]:
    async with system_rls_session() as db:
        user = await db.get(User, user_id)
    if user is None:
        return None, None
    organization_id = getattr(user, "organization_id", None)
    name = getattr(user, "name", None)
    teacher = name.strip() if isinstance(name, str) and name.strip() else None
    org_id = int(organization_id) if organization_id is not None else None
    return org_id, teacher


async def archive_assistant_reply(
    session: MindmateCollabSession,
    *,
    message_id: int,
    uploader_user_id: int,
    room_code: str,
) -> dict[str, object]:
    """Build or reuse the Word artifact for one assistant message, then broadcast it."""
    existing = await find_reply_artifact(session.id, message_id)
    if existing is not None:
        return existing
    markdown, user_prompt = await _assistant_reply(session.id, message_id)
    organization_id, teacher_name = await _uploader(uploader_user_id)
    payload, filename = await build_archived_reply_docx(
        markdown,
        user_prompt=user_prompt,
        user_id=uploader_user_id,
        organization_id=organization_id,
        teacher_name=teacher_name,
    )
    saved = await save_generated_background_file(
        session,
        uploader_user_id=uploader_user_id,
        uploader_name=teacher_name or "",
        filename=filename,
        data=payload,
        source_message_id=message_id,
    )
    await broadcast_to_all(room_code, {"type": "seminar_artifact", "file": saved})
    return saved


async def _archive_teaching_reply(
    *,
    code: str,
    session_id: str,
    message_id: int,
    uploader_user_id: int,
) -> None:
    session = await get_mindmate_collab_manager().load_session_by_id(session_id)
    if session is None:
        return
    try:
        await archive_assistant_reply(
            session,
            message_id=message_id,
            uploader_user_id=uploader_user_id,
            room_code=code,
        )
    except _ARCHIVE_ERRORS:
        logger.warning(
            "[SeminarArtifact] teaching-design archive failed session=%s message=%s",
            session_id,
            message_id,
            exc_info=True,
        )


def _consume_archive_task(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning("[SeminarArtifact] archive task failed: %s", error)


def schedule_teaching_reply_artifact(
    *,
    code: str,
    session_id: str,
    message_id: int,
    uploader_user_id: int,
) -> None:
    """Archive a finished teaching-design reply without blocking the chat stream."""
    task = asyncio.create_task(
        _archive_teaching_reply(
            code=code,
            session_id=session_id,
            message_id=message_id,
            uploader_user_id=uploader_user_id,
        ),
        name=f"seminar-reply-artifact:{message_id}",
    )
    task.add_done_callback(_consume_archive_task)
