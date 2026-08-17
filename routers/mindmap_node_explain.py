"""
Mind map node explain API — short everyday gloss stream for a selected node.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Type

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents.mind_maps.node_explain import get_mind_map_node_explain_generator
from models.domain.auth import User
from models.requests.requests_thinking import MindMapNodeExplainRequest
from routers.api.diagram_generation import assert_collab_blocks_canvas_ai
from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)
from services.monitoring.module_activity import track_module_activity
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth import get_current_user
from utils.chinese_language_policy import effective_language_for_thinking_user, is_chinese_ui_error_language

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)

_LOG_PREFIX = "[MindMapExplain]"

_LLM_ERROR_MAP: dict[Type[Exception], str] = {
    ThinkingCoinInsufficientError: "thinking_coin_insufficient",
    UserDailyTokenCapExceededError: "daily_token_cap",
    LLMContentFilterError: "content_filter",
    LLMRateLimitError: "rate_limit",
    LLMTimeoutError: "timeout",
    LLMInvalidParameterError: "invalid_parameter",
    LLMQuotaExhaustedError: "quota_exhausted",
    LLMModelNotFoundError: "model_not_found",
    LLMAccessDeniedError: "access_denied",
    LLMServiceError: "service_error",
}

_ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "thinking_coin_insufficient": (
        "思维币不足，请先获取思维币后再试。",
        "Not enough thinking coins. Earn more, then try again.",
    ),
    "daily_token_cap": (
        "今日 AI 用量已达上限，请明天再试。",
        "Daily AI usage limit reached. Please try again tomorrow.",
    ),
    "content_filter": (
        "无法处理您的请求，请尝试修改节点内容。",
        "Content could not be processed. Please try a different node.",
    ),
    "rate_limit": (
        "AI服务繁忙，请稍后重试。",
        "AI service is busy. Please try again in a few seconds.",
    ),
    "timeout": ("请求超时，请重试。", "Request timed out. Please try again."),
    "invalid_parameter": (
        "参数错误，请检查输入。",
        "Invalid parameter. Please check input.",
    ),
    "quota_exhausted": (
        "配额已用完，请检查账户。",
        "Quota exhausted. Please check account.",
    ),
    "model_not_found": (
        "模型不存在，请检查配置。",
        "Model not found. Please check configuration.",
    ),
    "access_denied": (
        "访问被拒绝，请检查权限。",
        "Access denied. Please check permissions.",
    ),
    "service_error": (
        "AI服务错误，请稍后重试。",
        "AI service error. Please try again later.",
    ),
    "unknown": ("出现问题，请重试。", "Something went wrong. Please try again."),
    "no_response": (
        "暂时没有生成内容。",
        "No response generated.",
    ),
    "collab_blocked": (
        "协作编辑期间无法使用 AI。",
        "AI generation is unavailable during live collaboration",
    ),
}


def _localized_error(error_type: str, language: str, user_message: str | None = None) -> str:
    if user_message and user_message.strip():
        return user_message.strip()
    zh_msg, en_msg = _ERROR_MESSAGES.get(error_type, _ERROR_MESSAGES["unknown"])
    return zh_msg if is_chinese_ui_error_language(language) else en_msg


def _error_sse(
    *,
    error_type: str,
    facet: str,
    language: str,
    user_message: str | None = None,
) -> str:
    msg = _localized_error(error_type, language, user_message)
    return (
        "data: "
        + json.dumps(
            {
                "event": "error",
                "error_type": error_type,
                "message": msg,
                "facet": facet,
            }
        )
        + "\n\n"
    )


def _resolve_error_type(exc: Exception) -> str:
    for exc_type, error_type in _LLM_ERROR_MAP.items():
        if isinstance(exc, exc_type):
            return error_type
    return "unknown"


async def _stream_explain(
    req: MindMapNodeExplainRequest,
    user: User | None,
):
    """Async generator yielding SSE chunks for one explain facet."""
    session_id = req.session_id.strip()
    facet = req.facet
    request_token = uuid.uuid4().hex[:12]
    session_short = session_id[:8]

    yield ": stream_open\n\n"

    diagram_id = getattr(req, "diagram_id", None)
    raw_lang = (getattr(req, "language", None) or "en").strip().lower()
    text_blobs = [
        req.node_label,
        req.topic,
        *(req.top_level_branches or []),
        *(req.ancestor_path or []),
        *(req.sibling_branches or []),
        *(req.child_branches or []),
    ]
    effective_lang = effective_language_for_thinking_user(user, raw_lang, *text_blobs)

    try:
        await assert_collab_blocks_canvas_ai(diagram_id, user)
    except HTTPException as exc:
        error_type = "collab_blocked" if exc.status_code == 403 else "unknown"
        msg = _localized_error(error_type, effective_lang, str(exc.detail) if exc.status_code != 403 else None)
        logger.warning(
            "%s Collab/guard blocked | session=%s facet=%s status=%s",
            _LOG_PREFIX,
            session_short,
            facet,
            exc.status_code,
        )
        yield _error_sse(
            error_type=error_type,
            facet=facet,
            language=effective_lang,
            user_message=msg,
        )
        return

    generator = get_mind_map_node_explain_generator()
    user_id = user.id if user and hasattr(user, "id") else None
    org_id = getattr(user, "organization_id", None) if user else None
    chunk_count = 0
    terminal_sent = False

    logger.info(
        "%s Stream start | session=%s facet=%s node=%s topic=%s user=%s",
        _LOG_PREFIX,
        session_short,
        facet,
        req.node_label[:24],
        (req.topic or "")[:24],
        user_id if user_id is not None else "-",
    )

    try:
        async for chunk in generator.stream_explain(
            node_label=req.node_label,
            topic=req.topic,
            diagram_type=req.diagram_type,
            top_level_branches=req.top_level_branches or [],
            ancestor_path=req.ancestor_path or [],
            sibling_branches=req.sibling_branches or [],
            child_branches=req.child_branches or [],
            language=effective_lang,
            facet=facet,
            user_id=user_id,
            organization_id=org_id,
            diagram_id=diagram_id,
            session_id=session_id,
            request_token=request_token,
            generation_instructions=req.generation_instructions,
        ):
            chunk_count += 1
            event = chunk.get("event")
            if event in ("end", "error"):
                terminal_sent = True
            yield f"data: {json.dumps(chunk)}\n\n"

        if chunk_count == 0 and not terminal_sent:
            terminal_sent = True
            logger.warning(
                "%s Empty stream | session=%s facet=%s",
                _LOG_PREFIX,
                session_short,
                facet,
            )
            yield _error_sse(
                error_type="no_response",
                facet=facet,
                language=effective_lang,
            )
        else:
            logger.info(
                "%s Stream complete | session=%s facet=%s chunks=%d",
                _LOG_PREFIX,
                session_short,
                facet,
                chunk_count,
            )

    except asyncio.CancelledError:
        logger.info(
            "%s Stream cancelled | session=%s facet=%s chunks=%d",
            _LOG_PREFIX,
            session_short,
            facet,
            chunk_count,
        )
        raise

    except (
        ThinkingCoinInsufficientError,
        UserDailyTokenCapExceededError,
        LLMContentFilterError,
        LLMRateLimitError,
        LLMTimeoutError,
        LLMInvalidParameterError,
        LLMQuotaExhaustedError,
        LLMModelNotFoundError,
        LLMAccessDeniedError,
        LLMServiceError,
    ) as exc:
        error_type = _resolve_error_type(exc)
        log_fn = logger.error if error_type in {"service_error", "unknown"} else logger.warning
        log_fn(
            "%s %s | session=%s facet=%s error=%s",
            _LOG_PREFIX,
            error_type,
            session_short,
            facet,
            str(exc),
        )
        yield _error_sse(
            error_type=error_type,
            facet=facet,
            language=effective_lang,
            user_message=getattr(exc, "user_message", None),
        )

    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error(
            "%s Stream error | session=%s facet=%s error=%s",
            _LOG_PREFIX,
            session_short,
            facet,
            str(exc),
            exc_info=True,
        )
        yield _error_sse(
            error_type="unknown",
            facet=facet,
            language=effective_lang,
        )


@router.post("/thinking_mode/mindmap/explain_node")
async def explain_mindmap_node(
    req: MindMapNodeExplainRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Stream a short everyday gloss for a mind map node."""
    session_id = req.session_id.strip()
    # Ephemeral assist: track live activity + logs only. Do not persist LLM text
    # (or usage-timeline previews) — results live in the bubble for this open only.
    await track_module_activity(
        user=current_user,
        module="canvas",
        redis_activity_type="mindmap_node_explain",
        request=request,
        details={
            "diagram_type": req.diagram_type,
            "session_id": session_id,
            "facet": req.facet,
            "node_label": req.node_label[:80],
        },
        detail=f"{req.facet} node={req.node_label[:24]} session={session_id[:8]}",
        persist_usage=False,
    )

    logger.debug(
        "%s Accept | session=%s facet=%s node=%s",
        _LOG_PREFIX,
        session_id[:8],
        req.facet,
        req.node_label[:24],
    )
    return StreamingResponse(
        _stream_explain(req, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
