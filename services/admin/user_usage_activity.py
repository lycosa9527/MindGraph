"""
Record and list curated user usage activities for admin timeline UI.

Writes use an isolated DB session so persistence failures never affect callers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.user_usage_activity import UserUsageActivity
from repositories.user_usage_activity_repo import UserUsageActivityRepository
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PREVIEW_MAX = 120
_TITLE_MAX = 200
_WHITESPACE_RE = re.compile(r"\s+")

_VALID_SOURCES = frozenset({"mindgraph", "mindmate", "dingtalk"})
_VALID_ACTIONS = frozenset(
    {
        "diagram_generate",
        "diagram_save",
        "chat_turn",
        "dingtalk_diagram",
    }
)


def clip_activity_preview(text: Optional[str], max_len: int = _PREVIEW_MAX) -> Optional[str]:
    """Normalize and truncate preview text for storage and display."""
    if text is None:
        return None
    collapsed = _WHITESPACE_RE.sub(" ", str(text)).strip()
    if not collapsed:
        return None
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1] + "…"


def clip_activity_title(text: Optional[str], max_len: int = _TITLE_MAX) -> Optional[str]:
    """Truncate diagram title / conversation name."""
    clipped = clip_activity_preview(text, max_len=max_len)
    if clipped is None:
        return None
    if len(clipped) <= max_len:
        return clipped
    return clipped[: max_len - 1] + "…"


def _normalize_source(source: str) -> Optional[str]:
    key = (source or "").strip().lower()
    if key in _VALID_SOURCES:
        return key
    return None


def _normalize_action(action: str) -> Optional[str]:
    key = (action or "").strip().lower()
    if key in _VALID_ACTIONS:
        return key
    return None


def activity_row_has_content(
    *,
    title: Optional[str],
    prompt_preview: Optional[str],
    reply_preview: Optional[str],
) -> bool:
    """Skip rows with no human-readable content."""
    return bool(
        (title and title.strip())
        or (prompt_preview and prompt_preview.strip())
        or (reply_preview and reply_preview.strip())
    )


async def record_user_usage_activity(
    *,
    user_id: int,
    organization_id: Optional[int],
    source: str,
    action: str,
    title: Optional[str] = None,
    prompt_preview: Optional[str] = None,
    reply_preview: Optional[str] = None,
    diagram_type: Optional[str] = None,
    diagram_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    total_tokens: Optional[int] = None,
    success: bool = True,
) -> None:
    """Fire-and-forget persist of one activity row (never raises to callers)."""
    if user_id <= 0:
        return
    norm_source = _normalize_source(source)
    norm_action = _normalize_action(action)
    if norm_source is None or norm_action is None:
        return

    clipped_title = clip_activity_title(title)
    clipped_prompt = clip_activity_preview(prompt_preview)
    clipped_reply = clip_activity_preview(reply_preview)
    if not activity_row_has_content(
        title=clipped_title,
        prompt_preview=clipped_prompt,
        reply_preview=clipped_reply,
    ):
        return

    dtype = (diagram_type or "").strip()[:50] or None
    did = (diagram_id or "").strip()[:36] or None
    conv = (conversation_id or "").strip()[:128] or None
    tokens = int(total_tokens) if total_tokens is not None and total_tokens >= 0 else None

    row = UserUsageActivity(
        user_id=int(user_id),
        organization_id=int(organization_id) if organization_id is not None else None,
        source=norm_source,
        action=norm_action,
        title=clipped_title,
        prompt_preview=clipped_prompt,
        reply_preview=clipped_reply,
        diagram_type=dtype,
        diagram_id=did,
        conversation_id=conv,
        total_tokens=tokens,
        success=bool(success),
    )
    try:
        async with system_rls_session() as session:
            repo = UserUsageActivityRepository(session)
            await repo.insert(row)
            await session.commit()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[UserUsageActivity] persist_failed user_id=%s source=%s action=%s error=%s",
            user_id,
            norm_source,
            norm_action,
            exc,
        )


def schedule_user_usage_activity(
    *,
    user_id: int,
    organization_id: Optional[int],
    source: str,
    action: str,
    title: Optional[str] = None,
    prompt_preview: Optional[str] = None,
    reply_preview: Optional[str] = None,
    diagram_type: Optional[str] = None,
    diagram_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    total_tokens: Optional[int] = None,
    success: bool = True,
) -> None:
    """Schedule a non-blocking activity persist (safe for request hot paths)."""
    asyncio.create_task(
        record_user_usage_activity(
            user_id=user_id,
            organization_id=organization_id,
            source=source,
            action=action,
            title=title,
            prompt_preview=prompt_preview,
            reply_preview=reply_preview,
            diagram_type=diagram_type,
            diagram_id=diagram_id,
            conversation_id=conversation_id,
            total_tokens=total_tokens,
            success=success,
        )
    )


async def list_user_usage_activities(
    db: AsyncSession,
    user_id: int,
    *,
    source: Optional[str] = None,
    limit: int = 50,
    before_id: Optional[int] = None,
) -> list[UserUsageActivity]:
    """Admin list: newest first with optional source filter."""
    repo = UserUsageActivityRepository(db)
    src = source.strip().lower() if isinstance(source, str) and source.strip() else None
    return await repo.list_for_user(
        user_id=int(user_id),
        limit=limit,
        before_id=before_id,
        source=src,
    )


def activity_to_admin_dict(row: UserUsageActivity) -> dict[str, Any]:
    """Serialize one row for admin JSON (camelCase keys)."""
    created = row.created_at
    created_iso = created.isoformat() if created is not None else None
    return {
        "id": int(row.id),
        "userId": int(row.user_id),
        "organizationId": int(row.organization_id) if row.organization_id is not None else None,
        "source": row.source,
        "action": row.action,
        "title": row.title,
        "promptPreview": row.prompt_preview,
        "replyPreview": row.reply_preview,
        "diagramType": row.diagram_type,
        "diagramId": row.diagram_id,
        "conversationId": row.conversation_id,
        "totalTokens": row.total_tokens,
        "success": bool(row.success),
        "createdAt": created_iso,
    }
