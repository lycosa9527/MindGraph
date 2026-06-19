"""Image proxy API — fetch whitelisted remote images for same-origin use."""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import ParseResult, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from config.settings import config
from routers.api.helpers import normalize_external_base_url
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_STATIC_ALLOWED_DOMAINS = frozenset(
    {
        "mg.mindspringedu.com",
    }
)

_DINGTALK_TEMP_IMAGE_PATH_RE = re.compile(
    r"/temp_images/dingtalk_[a-f0-9]{8}_\d+\.png",
    re.IGNORECASE,
)


def _is_loopback_hostname(hostname: str) -> bool:
    host = (hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    if host.startswith("127."):
        parts = host.split(".")
        if len(parts) != 4:
            return False
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
    return False


def _is_non_production_env() -> bool:
    env = (os.getenv("ENVIRONMENT") or "production").strip().lower()
    return config.debug or env in ("development", "test")


def allowed_image_proxy_domains() -> frozenset[str]:
    """Domains permitted for /api/proxy-image (static list + EXTERNAL_BASE_URL host)."""
    domains = set(_STATIC_ALLOWED_DOMAINS)
    external_base = normalize_external_base_url(os.getenv("EXTERNAL_BASE_URL", ""))
    if external_base:
        parsed = urlparse(external_base)
        if parsed.hostname:
            domains.add(parsed.hostname.lower())
    return frozenset(domains)


def _dev_local_temp_image_url_allowed(parsed: ParseResult) -> bool:
    """DEBUG/test: allow proxying loopback /temp_images/dingtalk_*.png (local dev UI)."""
    if not _is_non_production_env():
        return False
    if not _is_loopback_hostname(parsed.hostname or ""):
        return False
    path = parsed.path or ""
    return _DINGTALK_TEMP_IMAGE_PATH_RE.search(path) is not None


def _image_proxy_url_allowed(parsed: ParseResult) -> bool:
    domain = (parsed.hostname or "").lower()
    if domain in allowed_image_proxy_domains():
        return True
    return _dev_local_temp_image_url_allowed(parsed)


@router.get("/proxy-image")
async def proxy_image(url: str = Query(..., description="The image URL to proxy")):
    """
    Proxy an external image to avoid CORS/CORB issues in the MindMate UI.

    Security:
    - Only allows images from whitelisted domains
    - Redirects are not followed (prevents SSRF via redirect to internal URLs)
    - Only allows image content types
    - Limits response size to 10MB
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL")
    except BACKGROUND_INFRA_ERRORS as exc:
        raise HTTPException(status_code=400, detail="Invalid URL") from exc

    domain = parsed.netloc.split(":")[0]
    if not _image_proxy_url_allowed(parsed):
        logger.warning("Image proxy blocked for non-whitelisted domain: %s", domain)
        raise HTTPException(status_code=403, detail="Domain not allowed")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=False)

            if response.status_code != 200:
                if response.status_code in (301, 302, 303, 307, 308):
                    raise HTTPException(
                        status_code=400,
                        detail="Redirects are not followed; use the final image URL",
                    )
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch image")

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="URL does not point to an image")

            content_length = len(response.content)
            if content_length > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "X-Content-Type-Options": "nosniff",
                },
            )

    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timeout fetching image") from exc
    except httpx.RequestError as exc:
        logger.error("Error proxying image: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch image") from exc
