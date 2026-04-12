"""Web content mind map generation API (Chrome extension and API clients).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from agents.mind_maps.web_content_mind_map_agent import WebContentMindMapAgent
from models import Messages, WebContentGenerateRequest, WebContentMindmapPngRequest, get_request_language
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from utils.auth import get_current_user_or_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


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

    try:
        screenshot_bytes = await capture_diagram_screenshot(
            diagram_data=diagram_data,
            diagram_type="mind_map",
            width=req.width or 1200,
            height=req.height or 800,
        )
    except Exception as exc:
        logger.error("web_content_mindmap_png screenshot error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("export_failed", lang, str(exc))) from exc

    return Response(
        content=screenshot_bytes,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="mindgraph-web-content.png"'},
    )
