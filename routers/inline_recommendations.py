"""
Inline Recommendations API Router.

SSE endpoints for diagram auto-completion (mindmap, flow_map, tree_map, brace_map).
Catapult-style: fires 3 LLMs concurrently, streams recommendations progressively.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from agents.inline_recommendations import get_inline_recommendations_generator
from models.domain.auth import User
from models.requests.requests_thinking import (
    InlineRecommendationsStartRequest,
    InlineRecommendationsNextRequest,
    InlineRecommendationsCleanupRequest,
)
from services.infrastructure.http.error_handler import (
    LLMContentFilterError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceError,
)
from utils.auth import get_current_user
from utils.chinese_language_policy import (
    collect_inline_recommendation_text_blobs,
    effective_language_for_thinking_user,
    is_chinese_ui_error_language,
)

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)


async def _stream_recommendations(req, user: User | None, is_next: bool):
    """Async generator yielding SSE chunks from inline recommendations generator."""
    generator = get_inline_recommendations_generator()
    user_id = user.id if user and hasattr(user, "id") else None
    org_id = getattr(user, "organization_id", None) if user else None
    endpoint = (
        "/thinking_mode/inline_recommendations/next_batch" if is_next else "/thinking_mode/inline_recommendations/start"
    )
    chunk_count = 0
    rec_count = 0
    error_yielded = False
    raw_lang = (getattr(req, "language", None) or "en").strip().lower()
    text_blobs = collect_inline_recommendation_text_blobs(req)
    effective_lang = effective_language_for_thinking_user(user, raw_lang, *text_blobs)
    try:
        options = {
            "user_id": user_id,
            "organization_id": org_id,
            "endpoint_path": endpoint,
            "educational_context": getattr(req, "educational_context", None),
        }
        models = getattr(req, "models", None)
        rec_count = 0
        async for chunk in generator.generate_batch(
            session_id=req.session_id,
            diagram_type=req.diagram_type,
            stage=req.stage,
            nodes=req.nodes or [],
            connections=req.connections,
            current_node_id=req.node_id,
            language=effective_lang,
            count=getattr(req, "count", 15),
            models=models,
            options=options,
        ):
            chunk_count += 1
            if chunk.get("event") == "recommendation_generated":
                rec_count += 1
                logger.debug(
                    "[InlineRec] SSE yield #%d: %r",
                    rec_count,
                    chunk.get("text", "")[:60],
                )
            yield f"data: {json.dumps(chunk)}\n\n"
    except LLMContentFilterError as e:
        error_yielded = True
        msg = getattr(e, "user_message", None) or (
            "无法处理您的请求。"
            if is_chinese_ui_error_language(effective_lang)
            else "Content could not be processed."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMRateLimitError as e:
        error_yielded = True
        msg = getattr(e, "user_message", None) or (
            "AI服务繁忙，请稍后重试。"
            if is_chinese_ui_error_language(effective_lang)
            else "AI service busy. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMTimeoutError as e:
        error_yielded = True
        msg = getattr(e, "user_message", None) or (
            "请求超时，请重试。"
            if is_chinese_ui_error_language(effective_lang)
            else "Request timed out. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMServiceError as e:
        error_yielded = True
        msg = getattr(e, "user_message", None) or (
            "AI服务错误，请稍后重试。"
            if is_chinese_ui_error_language(effective_lang)
            else "AI service error. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except Exception as e:
        error_yielded = True
        logger.error("[InlineRec] Stream error: %s", str(e), exc_info=True)
        msg = (
            "请求失败，请重试。"
            if is_chinese_ui_error_language(effective_lang)
            else "Request failed. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    finally:
        logger.debug(
            "[InlineRec] Stream done: %d chunks, %d recommendations",
            chunk_count,
            rec_count,
        )
        if chunk_count == 0 and not error_yielded:
            yield f"data: {json.dumps({'event': 'error', 'message': 'No response'})}\n\n"


@router.post("/thinking_mode/inline_recommendations/start")
async def start_inline_recommendations(
    req: InlineRecommendationsStartRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Start inline recommendations generation - fires 3 LLMs concurrently.

    Returns SSE stream with recommendation_generated events.
    """
    logger.debug(
        "[InlineRec] Start: %s | Type: %s | Stage: %s | Node: %s",
        req.session_id[:8],
        req.diagram_type,
        req.stage,
        req.node_id[:20] if req.node_id else "",
    )

    return StreamingResponse(
        _stream_recommendations(req, current_user, is_next=False),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/thinking_mode/inline_recommendations/next_batch")
async def next_inline_recommendations_batch(
    req: InlineRecommendationsNextRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch next batch of inline recommendations.
    """
    logger.debug(
        "[InlineRec] Next batch: %s | Type: %s | Stage: %s",
        req.session_id[:8],
        req.diagram_type,
        req.stage,
    )

    return StreamingResponse(
        _stream_recommendations(req, current_user, is_next=True),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/thinking_mode/inline_recommendations/cleanup")
async def cleanup_inline_recommendations(
    req: InlineRecommendationsCleanupRequest,
    _current_user: User = Depends(get_current_user),
):
    """
    Clean up backend session state for given node IDs.
    """
    generator = get_inline_recommendations_generator()
    for nid in req.node_ids or []:
        generator.end_session(nid, reason="cleanup")
    logger.debug("[InlineRec] Cleanup: %d sessions", len(req.node_ids or []))
    return {"status": "cleaned", "count": len(req.node_ids or [])}
