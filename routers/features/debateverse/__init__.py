"""
DebateVerse Router - Debate Session Management and Streaming Endpoints
======================================================================

Provides API endpoints for creating and managing debate sessions,
streaming debater responses, and managing debate flow.

Uses MindGraph's centralized LLM infrastructure:
- Rate limiting (prevents quota exhaustion)
- Load balancing (DeepSeek → Dashscope/Volcengine, Kimi → Volcengine)
- Error handling (comprehensive error parsing)
- Token tracking (automatic usage tracking)

Chinese name: 论境
English name: DebateVerse

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.debateverse import DebateMessage, DebateParticipant, DebateSession
from prompts.debateverse import get_position_generation_prompt
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.debateverse.stream import stream_debater_response
from services.features.debateverse_service import DebateVerseService
from services.llm import llm_service
from services.monitoring.module_activity import schedule_module_activity
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth import get_current_user
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debateverse", tags=["DebateVerse"])

# ============================================================================
# Request/Response Models
# ============================================================================

_ALLOWED_DEBATE_FORMATS = frozenset({"us_parliamentary", "british_parliamentary", "lincoln_douglas"})
_ALLOWED_STAGES = frozenset(
    {
        "setup",
        "coin_toss",
        "opening",
        "rebuttal",
        "cross_exam",
        "closing",
        "judgment",
        "completed",
    }
)
_ALLOWED_MODELS = frozenset({"qwen", "deepseek", "kimi", "doubao"})
_ALLOWED_ROLES = frozenset({"debater", "judge", "viewer"})
_ALLOWED_SIDES = frozenset({"affirmative", "negative"})


class CreateSessionRequest(BaseModel):
    """Request model for creating a debate session."""

    topic: str = Field(..., min_length=1, max_length=500)
    llm_assignments: Dict[str, str] = Field(...)
    format: Optional[str] = Field("us_parliamentary")
    language: Optional[str] = Field("zh")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: Optional[str]) -> Optional[str]:
        """Allow only known debate formats."""
        if value and value not in _ALLOWED_DEBATE_FORMATS:
            raise ValueError(f"format must be one of: {', '.join(_ALLOWED_DEBATE_FORMATS)}")
        return value

    @field_validator("llm_assignments")
    @classmethod
    def validate_llm_assignments(cls, value: Dict[str, str]) -> Dict[str, str]:
        """Validate that model IDs are from the allowed set."""
        for model_id in value.values():
            if model_id not in _ALLOWED_MODELS:
                raise ValueError(f"Invalid model '{model_id}'. Allowed: {', '.join(_ALLOWED_MODELS)}")
        return value


class JoinSessionRequest(BaseModel):
    """Request model for joining a debate session."""

    role: Optional[str] = Field(None)
    side: Optional[str] = Field(None)
    position: Optional[int] = Field(None, ge=1, le=2)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        """Allow only known roles."""
        if value and value not in _ALLOWED_ROLES:
            raise ValueError(f"role must be one of: {', '.join(_ALLOWED_ROLES)}")
        return value

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: Optional[str]) -> Optional[str]:
        """Allow only known sides."""
        if value and value not in _ALLOWED_SIDES:
            raise ValueError(f"side must be one of: {', '.join(_ALLOWED_SIDES)}")
        return value


class SendMessageRequest(BaseModel):
    """Request model for sending a message in a debate session."""

    content: str = Field(..., min_length=1, max_length=5000)


class AdvanceStageRequest(BaseModel):
    """Request model for advancing debate stage."""

    new_stage: str = Field(...)

    @field_validator("new_stage")
    @classmethod
    def validate_new_stage(cls, value: str) -> str:
        """Allow only known stage values."""
        if value not in _ALLOWED_STAGES:
            raise ValueError(f"new_stage must be one of: {', '.join(_ALLOWED_STAGES)}")
        return value


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Create a new debate session. Requires authentication."""

    try:
        service = DebateVerseService("", db)
        session = await service.create_debate_session(
            topic=request.topic,
            user_id=current_user.id,
            llm_assignments=request.llm_assignments,
            debate_format=request.format or "us_parliamentary",
        )
        schedule_module_activity(
            user=current_user,
            module="debateverse",
            redis_activity_type="debateverse",
            details={"session_id": session.id, "action": "create"},
            detail=f"create session={session.id}",
            usage_source="mindgraph",
            usage_action="debate_turn",
            title=request.topic,
            prompt_preview=request.topic,
            conversation_id=session.id,
        )

        return {
            "session_id": session.id,
            "topic": session.topic,
            "current_stage": session.current_stage,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
        }
    except DATABASE_ERRORS as e:
        logger.error("Error creating debate session: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create debate session") from e


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
    _current_user=Depends(get_current_user),
):
    """Get debate session with messages and participants. Requires authentication."""
    session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    participants = (
        (await db.execute(select(DebateParticipant).where(DebateParticipant.session_id == session_id))).scalars().all()
    )

    messages = (
        (
            await db.execute(
                select(DebateMessage).where(DebateMessage.session_id == session_id).order_by(DebateMessage.created_at)
            )
        )
        .scalars()
        .all()
    )

    return {
        "session": {
            "id": session.id,
            "topic": session.topic,
            "current_stage": session.current_stage,
            "status": session.status,
            "coin_toss_result": session.coin_toss_result,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        },
        "participants": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "side": p.side,
                "is_ai": p.is_ai,
                "model_id": p.model_id,
            }
            for p in participants
        ],
        "messages": [
            {
                "id": m.id,
                "participant_id": m.participant_id,
                "content": m.content,
                "thinking": m.thinking,
                "stage": m.stage,
                "round_number": m.round_number,
                "message_type": m.message_type,
                "audio_url": m.audio_url,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.post("/sessions/{session_id}/coin-toss")
async def coin_toss(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Execute coin toss to determine speaking order. Requires authentication."""
    session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this session")
    service = DebateVerseService(session_id, db)
    result = await service.coin_toss()

    return {
        "result": result,
        "message": "affirmative_first" if result == "affirmative_first" else "negative_first",
    }


@router.get("/sessions/{session_id}/generate-positions")
async def generate_positions(
    session_id: str,
    request: Request,
    language: str = Query("zh", description="Language for position generation"),
    current_user=Depends(get_current_user),
):
    """
    Generate debate positions using Doubao LLM with SSE streaming.
    Requires authentication. Rate limited to 30 requests/min per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)

    async with user_rls_session(current_user.id) as db:
        session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        debate_topic = session.topic or "辩论主题"

    async def generate():
        try:
            await check_endpoint_rate_limit(
                "debateverse_positions",
                identifier,
                max_requests=30,
                window_seconds=60,
            )

            logger.info(
                "[DEBATEVERSE] Generating positions for session %s, topic: %s",
                session_id,
                debate_topic,
            )

            prompt = get_position_generation_prompt(topic=debate_topic, language=language)

            async for chunk in llm_service.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                model="doubao",
                temperature=0.7,
                max_tokens=1000,
                enable_thinking=False,
                yield_structured=True,
                user_id=current_user.id,
                request_type="debateverse",
                endpoint_path=f"/api/debateverse/sessions/{session_id}/generate-positions",
            ):
                if isinstance(chunk, dict):
                    chunk_type = chunk.get("type")
                    if chunk_type == "token":
                        content = chunk.get("content", "")
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except asyncio.CancelledError:
            logger.info("[DEBATEVERSE] Position generation cancelled for session %s", session_id)
            raise
        except HTTPException as exc:
            logger.warning("[DEBATEVERSE] Position generation rejected: %s", exc.detail)
            yield f"data: {json.dumps({'type': 'error', 'error': exc.detail})}\n\n"
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.error("[DEBATEVERSE] Position generation error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': 'Internal server error'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/advance-stage")
async def advance_stage(
    session_id: str,
    request: AdvanceStageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Advance debate to next stage. Requires authentication and session ownership."""
    session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this session")
    service = DebateVerseService(session_id, db)
    success = await service.advance_stage(request.new_stage)

    if not success:
        raise HTTPException(status_code=400, detail="Invalid stage transition")

    return {"success": True, "new_stage": request.new_stage}


@router.post("/sessions/{session_id}/messages")
async def send_user_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Send a user message in the debate session. Requires authentication."""

    session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_participant = (
        await db.execute(
            select(DebateParticipant).where(
                DebateParticipant.session_id == session_id,
                DebateParticipant.user_id == current_user.id,
                DebateParticipant.is_ai.is_(False),
            )
        )
    ).scalar_one_or_none()

    if not user_participant:
        raise HTTPException(status_code=403, detail="User is not a participant in this session")

    current_stage = session.current_stage
    service = DebateVerseService(session_id, db)
    round_number = await service.get_next_round_number(current_stage)
    message_type = service.get_message_type_for_stage(current_stage)

    message = DebateMessage(
        session_id=session_id,
        participant_id=user_participant.id,
        content=request.content,
        stage=current_stage,
        round_number=round_number,
        message_type=message_type,
    )
    db.add(message)
    try:
        await db.commit()
    except DATABASE_ERRORS:
        await db.rollback()
        raise

    schedule_module_activity(
        user=current_user,
        module="debateverse",
        redis_activity_type="debateverse",
        details={"session_id": session_id, "action": "message", "stage": current_stage},
        detail=f"message session={session_id} stage={current_stage}",
        usage_source="mindgraph",
        usage_action="debate_turn",
        title=f"debate:{session_id[:8]}",
        prompt_preview=request.content,
        conversation_id=session_id,
    )

    return {
        "success": True,
        "message_id": message.id,
        "message": {
            "id": message.id,
            "participant_id": message.participant_id,
            "content": message.content,
            "stage": message.stage,
            "round_number": message.round_number,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat(),
        },
    }


@router.post("/next")
async def trigger_next(
    session_id: str = Query(...),
    language: str = Query("zh"),
    db: AsyncSession = Depends(get_async_db),
    _current_user=Depends(get_current_user),
):
    """
    Trigger next conversation in debate.
    Returns next speaker info for immediate streaming, or indicates stage completion.
    """
    logger.info("Trigger next called for session %s", session_id)

    session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
    if not session:
        logger.error("Session %s not found in database", session_id)
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Session found: %s, current_stage: %s", session.id, session.current_stage)

    service = DebateVerseService(session_id, db)

    next_speaker = await service.get_next_speaker(session.current_stage)

    if next_speaker:
        return {
            "action": "trigger_speaker",
            "has_next_speaker": True,
            "participant_id": next_speaker.id,
            "participant_name": next_speaker.name,
            "participant_role": next_speaker.role,
            "participant_side": next_speaker.side,
            "stage": session.current_stage,
            "language": language,
        }

    stage_order = [
        "setup",
        "coin_toss",
        "opening",
        "rebuttal",
        "cross_exam",
        "closing",
        "judgment",
        "completed",
    ]
    current_index = stage_order.index(session.current_stage) if session.current_stage in stage_order else -1

    if current_index < len(stage_order) - 1:
        next_stage = stage_order[current_index + 1]
        return {
            "action": "advance_stage",
            "has_next_speaker": False,
            "stage_complete": True,
            "next_stage": next_stage,
            "current_stage": session.current_stage,
        }
    return {
        "action": "complete",
        "has_next_speaker": False,
        "stage_complete": True,
        "debate_complete": True,
        "current_stage": session.current_stage,
    }


@router.post("/sessions/{session_id}/stream/{participant_id}")
async def stream_debater(
    session_id: str,
    participant_id: int,
    stage: str,
    request: Request,
    language: str = "zh",
    current_user=Depends(get_current_user),
):
    """Stream debater response. Requires authentication and session ownership."""
    async with user_rls_session(current_user.id) as db:
        session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this session")

    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("debateverse_stream", identifier, max_requests=60, window_seconds=60)

    schedule_module_activity(
        user=current_user,
        module="debateverse",
        redis_activity_type="debateverse",
        request=request,
        details={"session_id": session_id, "action": "stream", "stage": stage},
        detail=f"stream session={session_id} stage={stage}",
        usage_source="mindgraph",
        usage_action="debate_turn",
        title=f"stream:{stage}",
        prompt_preview=f"debater={participant_id} stage={stage}",
        conversation_id=session_id,
    )

    return StreamingResponse(
        stream_debater_response(
            session_id=session_id,
            participant_id=participant_id,
            stage=stage,
            language=language,
            user_id=current_user.id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
):
    """List user's debate sessions. Requires authentication."""

    sessions = (
        (
            await db.execute(
                select(DebateSession)
                .where(DebateSession.user_id == current_user.id)
                .order_by(DebateSession.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    total = (
        await db.execute(select(sa_count(DebateSession.id)).where(DebateSession.user_id == current_user.id))
    ).scalar()

    return {
        "sessions": [
            {
                "id": s.id,
                "topic": s.topic,
                "current_stage": s.current_stage,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ],
        "total": total,
    }
