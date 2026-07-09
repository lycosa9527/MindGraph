"""
Mind map node explain API — concise Kitty helper for a single node.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from agents.mind_maps.node_explain import get_mind_map_node_explain_generator
from models.domain.auth import User
from models.requests.requests_thinking import MindMapNodeExplainRequest
from routers.api.diagram_generation import assert_collab_blocks_canvas_ai
from services.infrastructure.http.error_handler import (
    LLMContentFilterError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth import get_current_user
from utils.chinese_language_policy import effective_language_for_thinking_user, is_chinese_ui_error_language

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)


async def _stream_explain(req: MindMapNodeExplainRequest, user: User | None):
    """Async generator yielding SSE chunks for node explain."""
    diagram_id = getattr(req, "diagram_id", None)
    try:
        await assert_collab_blocks_canvas_ai(diagram_id, user)
    except HTTPException as exc:
        msg = "AI generation is unavailable during live collaboration" if exc.status_code == 403 else str(exc.detail)
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
        return

    generator = get_mind_map_node_explain_generator()
    user_id = user.id if user and hasattr(user, "id") else None
    org_id = getattr(user, "organization_id", None) if user else None
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
    chunk_count = 0

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
            user_id=user_id,
            organization_id=org_id,
            diagram_id=diagram_id,
            history=[{"role": turn.role, "content": turn.content} for turn in (req.history or [])],
            user_message=req.user_message,
        ):
            chunk_count += 1
            yield f"data: {json.dumps(chunk)}\n\n"
    except LLMContentFilterError as exc:
        msg = getattr(exc, "user_message", None) or (
            "无法处理您的请求。" if is_chinese_ui_error_language(effective_lang) else "Content could not be processed."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMRateLimitError as exc:
        msg = getattr(exc, "user_message", None) or (
            "AI服务繁忙，请稍后重试。"
            if is_chinese_ui_error_language(effective_lang)
            else "AI service busy. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMTimeoutError as exc:
        msg = getattr(exc, "user_message", None) or (
            "请求超时，请重试。" if is_chinese_ui_error_language(effective_lang) else "Request timed out. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMServiceError as exc:
        msg = getattr(exc, "user_message", None) or (
            "AI服务错误，请稍后重试。"
            if is_chinese_ui_error_language(effective_lang)
            else "AI service error. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[MindMapExplain] Stream error: %s", str(exc), exc_info=True)
        msg = "请求失败，请重试。" if is_chinese_ui_error_language(effective_lang) else "Request failed. Please retry."
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    finally:
        if chunk_count == 0:
            yield f"data: {json.dumps({'event': 'error', 'message': 'No response'})}\n\n"


@router.post("/thinking_mode/mindmap/explain_node")
async def explain_mindmap_node(
    req: MindMapNodeExplainRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream a concise Kitty-style explanation for one mind map node."""
    logger.debug(
        "[MindMapExplain] node=%s topic=%s",
        req.node_label[:24],
        (req.topic or "")[:24],
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
