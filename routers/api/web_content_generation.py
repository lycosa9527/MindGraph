"""Web content mind map generation API (Chrome extension and API clients).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from agents.mind_maps.web_content_mind_map_agent import WebContentMindMapAgent
from models import Messages, WebContentGenerateRequest, WebContentMindmapPngRequest, get_request_language
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth import get_current_user_or_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_SAVE_LIMIT_REACHED = "__limit_reached__"


async def _try_save_to_library(
    user_id: Optional[int],
    title: str,
    diagram_data: dict,
    language: str,
    http_request_id: Optional[str],
) -> Optional[str]:
    """Save generated spec to the user's diagram library.

    Returns the new diagram ID on success, _SAVE_LIMIT_REACHED when the user
    has hit their quota, or None for anonymous users or on transient failures.
    Never raises so it is safe to run concurrently with screenshot capture via
    asyncio.gather.
    """
    if user_id is None:
        return None
    try:
        cache = get_diagram_cache()
        save_ok, new_id, save_err = await cache.save_diagram(
            user_id=user_id,
            diagram_id=None,
            title=title,
            diagram_type="mind_map",
            spec=diagram_data,
            language=language,
            thumbnail=None,
        )
        if save_ok and new_id:
            return str(new_id)
        if "limit reached" in (save_err or "").lower():
            logger.info(
                "web_content_mindmap_png: library full user=%s request_id=%s",
                user_id,
                http_request_id or "none",
            )
            return _SAVE_LIMIT_REACHED
        logger.warning(
            "web_content_mindmap_png: library save failed user=%s request_id=%s: %s",
            user_id,
            http_request_id or "none",
            save_err,
        )
        return None
    except Exception as save_exc:
        logger.warning(
            "web_content_mindmap_png: library save error user=%s request_id=%s: %s",
            user_id,
            http_request_id or "none",
            save_exc,
        )
        return None


def _sanitize_correlation_header(value: Optional[str], max_len: int = 128) -> Optional[str]:
    """Normalize X-Request-Id / client hints for logs and LLM metadata."""
    if not value or not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped[:max_len]


@router.post("/generate_from_web_content")
async def generate_from_web_content(
    req: WebContentGenerateRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Generate a mind map specification from extracted web page text (mind map only).

    Rate limited: 100 requests per minute per user/IP.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("generate_from_web_content", identifier, max_requests=100, window_seconds=60)

    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )

    http_request_id = _sanitize_correlation_header(request.headers.get("X-Request-Id"))

    agent = WebContentMindMapAgent(model="qwen")
    result = await agent.generate_from_page_content(
        page_content=req.page_content.strip(),
        language=req.language,
        content_format=req.content_format,
        page_title=req.page_title,
        page_url=req.page_url,
        user_id=user_id,
        organization_id=organization_id,
        request_type="diagram_generation",
        endpoint_path="/api/generate_from_web_content",
        http_request_id=http_request_id,
    )

    if not result.get("success"):
        detail = result.get("error") or "Generation failed"
        raise HTTPException(status_code=500, detail=detail)

    return result


@router.post("/web_content_mindmap_png")
async def web_content_mindmap_png(
    req: WebContentMindmapPngRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Generate mind map from web page text and return a PNG file (single round-trip).

    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("web_content_mindmap_png", identifier, max_requests=100, window_seconds=60)

    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)

    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )

    http_request_id = _sanitize_correlation_header(request.headers.get("X-Request-Id"))
    client_label = _sanitize_correlation_header(request.headers.get("X-MG-Client"), max_len=64) or "unspecified"
    logger.info(
        "[TokenAudit] web_content_mindmap_png: user=%s, client=%s, request_id=%s",
        user_id if user_id is not None else "anonymous",
        client_label,
        http_request_id or "none",
    )

    agent = WebContentMindMapAgent(model="qwen")
    result = await agent.generate_from_page_content(
        page_content=req.page_content.strip(),
        language=req.language,
        content_format=req.content_format,
        page_title=req.page_title,
        page_url=req.page_url,
        user_id=user_id,
        organization_id=organization_id,
        request_type="diagram_generation",
        endpoint_path="/api/web_content_mindmap_png",
        http_request_id=http_request_id,
    )

    if not result.get("success"):
        detail = result.get("error") or "Generation failed"
        raise HTTPException(status_code=500, detail=detail)

    spec = result.get("spec")
    if not isinstance(spec, dict):
        raise HTTPException(status_code=500, detail=Messages.error("internal_error", lang))

    diagram_data = dict(spec)
    if isinstance(diagram_data, dict):
        if "is_learning_sheet" not in diagram_data:
            diagram_data["is_learning_sheet"] = False
        if "hidden_node_percentage" not in diagram_data:
            diagram_data["hidden_node_percentage"] = 0

    title = (req.page_title or "").strip()[:200] or "Web Content Mind Map"

    screenshot_result, saved_diagram_id = await asyncio.gather(
        capture_diagram_screenshot(
            diagram_data=diagram_data,
            diagram_type="mind_map",
            width=req.width or 1200,
            height=req.height or 800,
        ),
        _try_save_to_library(user_id, title, diagram_data, req.language, http_request_id),
        return_exceptions=True,
    )

    if isinstance(screenshot_result, BaseException):
        exc = screenshot_result
        logger.error(
            "web_content_mindmap_png screenshot error: request_id=%s %s",
            http_request_id or "none",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=Messages.error("export_failed", lang, str(exc))
        ) from exc

    screenshot_bytes: bytes = screenshot_result
    save_error_type: Optional[str] = None
    if saved_diagram_id == _SAVE_LIMIT_REACHED:
        save_error_type = "limit_reached"
        saved_diagram_id = None
    elif not isinstance(saved_diagram_id, str):
        saved_diagram_id = None

    response_headers: dict = {"Content-Disposition": 'attachment; filename="mindgraph-web-content.png"'}
    if saved_diagram_id:
        response_headers["X-MG-Diagram-Id"] = saved_diagram_id
    if save_error_type:
        response_headers["X-MG-Save-Error"] = save_error_type

    return Response(
        content=screenshot_bytes,
        media_type="image/png",
        headers=response_headers,
    )
