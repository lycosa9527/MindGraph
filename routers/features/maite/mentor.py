"""
Mate Learning mentor decompose and follow-up endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.maite.helpers import (
    MAITE_DOMAIN_ERRORS,
    organization_id_for,
    raise_maite_http_error,
    stream_maite_events,
)
from services.maite.domain.mentor_service import MentorService
from services.maite.schemas.mentor import (
    MentorDecomposeInput,
    MentorFollowUpInput,
)
from services.monitoring.module_activity import schedule_module_activity
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class MentorFollowUpRequest(MentorFollowUpInput):
    """Follow-up payload including prior decomposition context."""

    decomposition: dict[str, Any] = Field(default_factory=dict)


def _schedule_mentor_activity(
    *,
    user: User,
    request: Request,
    action: str,
    preview: str,
) -> None:
    schedule_module_activity(
        user=user,
        module="maite",
        redis_activity_type="maite",
        request=request,
        details={"action": action},
        detail=action,
        usage_source="mindgraph",
        usage_action="maite_mentor",
        title=f"maite:{action}",
        prompt_preview=preview[:120] if preview else None,
    )


@router.post("/mentor/decompose")
async def decompose_problem(
    payload: MentorDecomposeInput,
    request: Request,
    _db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Run mentor reverse-decompose (non-streaming)."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("maite_mentor", identifier, max_requests=60, window_seconds=60)
    _schedule_mentor_activity(user=current_user, request=request, action="decompose", preview=payload.question)
    service = MentorService()
    try:
        logger.info("[Maite] Mentor decompose start user=%s", current_user.id)
        result = await service.decompose(
            payload,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path="/api/maite/mentor/decompose",
        )
        logger.info("[Maite] Mentor decompose complete user=%s", current_user.id)
        return result
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/mentor/decompose/stream")
async def decompose_problem_stream(
    payload: MentorDecomposeInput,
    request: Request,
    _db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream mentor reverse-decompose as SSE (status/preview/complete/error)."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("maite_mentor_stream", identifier, max_requests=60, window_seconds=60)
    _schedule_mentor_activity(user=current_user, request=request, action="decompose_stream", preview=payload.question)
    logger.info("[Maite] Mentor decompose stream start user=%s", current_user.id)
    service = MentorService()
    events = service.decompose_stream(
        payload,
        user_id=current_user.id,
        organization_id=organization_id_for(current_user),
        endpoint_path="/api/maite/mentor/decompose/stream",
    )
    return StreamingResponse(
        stream_maite_events(events),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/mentor/follow-up")
async def answer_follow_up(
    payload: MentorFollowUpRequest,
    request: Request,
    _db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Run mentor follow-up (non-streaming)."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("maite_mentor", identifier, max_requests=60, window_seconds=60)
    _schedule_mentor_activity(user=current_user, request=request, action="follow_up", preview=payload.reply)
    service = MentorService()
    try:
        logger.info("[Maite] Mentor follow-up start user=%s", current_user.id)
        result = await service.follow_up(
            payload,
            decomposition=payload.decomposition,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            endpoint_path="/api/maite/mentor/follow-up",
        )
        logger.info("[Maite] Mentor follow-up complete user=%s", current_user.id)
        return result
    except (*MAITE_DOMAIN_ERRORS,) as exc:
        raise_maite_http_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/mentor/follow-up/stream")
async def answer_follow_up_stream(
    payload: MentorFollowUpRequest,
    request: Request,
    _db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream mentor follow-up as SSE (status/preview/complete/error)."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("maite_mentor_stream", identifier, max_requests=60, window_seconds=60)
    _schedule_mentor_activity(user=current_user, request=request, action="follow_up_stream", preview=payload.reply)
    logger.info("[Maite] Mentor follow-up stream start user=%s", current_user.id)
    service = MentorService()
    events = service.follow_up_stream(
        payload,
        decomposition=payload.decomposition,
        user_id=current_user.id,
        organization_id=organization_id_for(current_user),
        endpoint_path="/api/maite/mentor/follow-up/stream",
    )
    return StreamingResponse(
        stream_maite_events(events),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
