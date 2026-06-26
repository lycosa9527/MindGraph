"""Web content mind map generation API (Chrome extension and API clients).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import ipaddress
import logging
import re
import socket
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from agents.mind_maps.web_content_mind_map_agent import WebContentMindMapAgent
from models import (
    CanvasDocumentMindmapRequest,
    Messages,
    WebContentGenerateRequest,
    WebContentMindmapPngRequest,
    get_request_language,
)
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from services.knowledge.document_processor import DocumentProcessor
from services.admin.user_usage_activity import schedule_user_usage_activity
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import REDIS_ERRORS
from utils.auth import get_current_user, get_current_user_or_api_key
from utils.auth.school_tier import (
    TIER_FEATURE_CHROME_EXTENSION,
    assert_user_has_school_tier_feature,
)
from utils.db.session_open import actor_rls_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_SAVE_LIMIT_REACHED = "__limit_reached__"
_MAX_FETCH_BYTES = 2 * 1024 * 1024
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_DOC_BYTES = 20 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg"}
_ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor for web page fetch."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        """Join extracted text chunks into a single plain-text document."""
        return re.sub(r"\n{3,}", "\n\n", "\n".join(self._chunks)).strip()


def _is_blocked_fetch_host(host: str) -> bool:
    """Reject localhost and private/reserved IPs to reduce SSRF risk."""
    lowered = (host or "").strip().lower()
    if lowered in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        for info in socket.getaddrinfo(host, None):
            ip_str = info[4][0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
    except OSError:
        return True
    return False


async def _fetch_url_page_text(url: str) -> Tuple[str, Optional[str]]:
    """Fetch a public web page and return plain text plus document title."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")

    host = parsed.hostname or ""
    if _is_blocked_fetch_host(host):
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    headers = {
        "User-Agent": "MindGraphCanvas/1.0 (+https://mg.mindspringedu.com)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False, headers=headers) as client:
            response = await client.get(url.strip())
            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail="Failed to fetch page")
            if len(response.content) > _MAX_FETCH_BYTES:
                raise HTTPException(status_code=413, detail="Page too large")

            content_type = (response.headers.get("content-type") or "").lower()
            raw = response.text

            if "text/plain" in content_type or "application/json" in content_type:
                text = raw.strip()
            else:
                parser = _HTMLTextExtractor()
                parser.feed(raw)
                text = parser.get_text()

            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None

            if not text:
                raise HTTPException(status_code=422, detail="No readable text found on page")
            return text[:32000], title
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timeout fetching page") from exc
    except httpx.RequestError as exc:
        logger.warning("canvas document summary fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch page") from exc


async def _resolve_canvas_page_content(req: CanvasDocumentMindmapRequest) -> Tuple[str, Optional[str], Optional[str]]:
    """Resolve text content from paste/upload or by fetching a URL."""
    content = (req.page_content or "").strip()
    title = req.page_title
    page_url = (req.page_url or "").strip() or None

    if content:
        return content, title, page_url

    if page_url:
        fetched_content, fetched_title = await _fetch_url_page_text(page_url)
        return fetched_content, fetched_title or title, page_url

    raise HTTPException(status_code=400, detail="Either page_content or page_url is required")


async def _generate_mindmap_from_resolved_content(
    *,
    page_content: str,
    language: str,
    content_format: str,
    page_title: Optional[str],
    page_url: Optional[str],
    request: Request,
    current_user: Optional[User],
    endpoint_path: str,
    rate_limit_key: str,
    require_chrome_tier: bool,
) -> dict:
    """Shared mind map generation from resolved page text."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(rate_limit_key, identifier, max_requests=100, window_seconds=60)

    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(None, accept_language)

    if require_chrome_tier and current_user is not None:
        async with actor_rls_session(current_user) as db:
            await assert_user_has_school_tier_feature(
                db,
                current_user,
                TIER_FEATURE_CHROME_EXTENSION,
                lang,
            )

    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )

    http_request_id = _sanitize_correlation_header(request.headers.get("X-Request-Id"))

    agent = WebContentMindMapAgent(model="qwen")
    result = await agent.generate_from_page_content(
        page_content=page_content.strip(),
        language=language,
        content_format=content_format,
        page_title=page_title,
        page_url=page_url,
        user_id=user_id,
        organization_id=organization_id,
        request_type="diagram_generation",
        endpoint_path=endpoint_path,
        http_request_id=http_request_id,
    )

    if not result.get("success"):
        detail = result.get("error") or "Generation failed"
        raise HTTPException(status_code=500, detail=detail)

    if user_id:
        title_preview = (page_title or page_url or "").strip()[:200] or None
        schedule_user_usage_activity(
            user_id=int(user_id),
            organization_id=organization_id,
            source="mindgraph",
            action="diagram_generate",
            title=title_preview,
            prompt_preview=title_preview,
            diagram_type="mind_map",
        )

    return result


async def _try_save_to_library(
    user_id: Optional[int],
    title: str,
    diagram_data: dict,
    language: str,
    http_request_id: Optional[str],
    organization_id: Optional[int] = None,
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
            organization_id=organization_id,
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
    except REDIS_ERRORS as save_exc:
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
    return await _generate_mindmap_from_resolved_content(
        page_content=req.page_content.strip(),
        language=req.language,
        content_format=req.content_format,
        page_title=req.page_title,
        page_url=req.page_url,
        request=request,
        current_user=current_user,
        endpoint_path="/api/generate_from_web_content",
        rate_limit_key="generate_from_web_content",
        require_chrome_tier=True,
    )


@router.post("/canvas/generate_mindmap_from_document")
async def canvas_generate_mindmap_from_document(
    req: CanvasDocumentMindmapRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Canvas document summary panel — text paste, uploaded doc, or web URL."""
    page_content, page_title, page_url = await _resolve_canvas_page_content(req)
    return await _generate_mindmap_from_resolved_content(
        page_content=page_content,
        language=req.language,
        content_format=req.content_format,
        page_title=page_title,
        page_url=page_url,
        request=request,
        current_user=current_user,
        endpoint_path="/api/canvas/generate_mindmap_from_document",
        rate_limit_key="canvas_generate_mindmap_from_document",
        require_chrome_tier=False,
    )


@router.post("/canvas/generate_mindmap_from_document_file")
async def canvas_generate_mindmap_from_document_file(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("zh"),
    current_user: User = Depends(get_current_user),
):
    """Canvas document summary panel — extract PDF/DOCX text then generate mind map."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > _MAX_DOC_BYTES:
        raise HTTPException(status_code=413, detail="Document too large")

    suffix = Path(file.filename or "upload.pdf").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Unsupported document type")

    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            temp_path = Path(tmp.name)

        processor = DocumentProcessor()
        file_type = processor.get_file_type(str(temp_path))
        if file_type not in _ALLOWED_DOC_TYPES or not processor.is_supported(file_type):
            raise HTTPException(status_code=400, detail="Unsupported document type")

        extracted = processor.extract_text(str(temp_path), file_type)
        if not extracted or not extracted.strip():
            raise HTTPException(status_code=422, detail="No text extracted from document")

        page_title = (file.filename or "Document").strip()[:500]
        return await _generate_mindmap_from_resolved_content(
            page_content=extracted.strip()[:32000],
            language=language,
            content_format="text/plain",
            page_title=page_title,
            page_url=None,
            request=request,
            current_user=current_user,
            endpoint_path="/api/canvas/generate_mindmap_from_document_file",
            rate_limit_key="canvas_generate_mindmap_from_document_file",
            require_chrome_tier=False,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.post("/canvas/generate_mindmap_from_image")
async def canvas_generate_mindmap_from_image(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("zh"),
    current_user: User = Depends(get_current_user),
):
    """Canvas document summary panel — OCR image text then generate mind map."""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            temp_path = Path(tmp.name)

        processor = DocumentProcessor()
        extracted = processor.extract_text(str(temp_path), file.content_type or "image/jpeg")
        if not extracted or not extracted.strip():
            raise HTTPException(status_code=422, detail="No text extracted from image")

        page_title = (file.filename or "Image").strip()[:500]
        return await _generate_mindmap_from_resolved_content(
            page_content=extracted.strip()[:32000],
            language=language,
            content_format="text/plain",
            page_title=page_title,
            page_url=None,
            request=request,
            current_user=current_user,
            endpoint_path="/api/canvas/generate_mindmap_from_image",
            rate_limit_key="canvas_generate_mindmap_from_image",
            require_chrome_tier=False,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


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

    if current_user is not None:
        async with actor_rls_session(current_user) as db:
            await assert_user_has_school_tier_feature(
                db,
                current_user,
                TIER_FEATURE_CHROME_EXTENSION,
                lang,
            )

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
        _try_save_to_library(
            user_id,
            title,
            diagram_data,
            req.language,
            http_request_id,
            organization_id,
        ),
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
        raise HTTPException(status_code=500, detail=Messages.error("export_failed", lang, str(exc))) from exc

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

    if user_id:
        schedule_user_usage_activity(
            user_id=int(user_id),
            organization_id=organization_id,
            source="mindgraph",
            action="diagram_generate",
            title=title,
            prompt_preview=title,
            diagram_type="mind_map",
            diagram_id=saved_diagram_id,
        )

    return Response(
        content=screenshot_bytes,
        media_type="image/png",
        headers=response_headers,
    )
