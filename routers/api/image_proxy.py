"""Image proxy API — fetch whitelisted remote images for same-origin use."""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import ParseResult, parse_qs, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from config.settings import config
from routers.api.helpers import normalize_external_base_url
from routers.api.png_export import serve_temp_image
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.public_hosts import FIRST_PARTY_PUBLIC_HOSTS, rewrite_legacy_public_origin
from utils.public_https_url import is_loopback_host, upgrade_public_http_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_STATIC_ALLOWED_DOMAINS = FIRST_PARTY_PUBLIC_HOSTS

_DINGTALK_TEMP_IMAGE_PATH_RE = re.compile(
    r"/temp_images/dingtalk_[a-f0-9]{8}_\d+\.png",
    re.IGNORECASE,
)


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
    """DEBUG only: allow proxying loopback /temp_images/dingtalk_*.png (local dev UI)."""
    if not config.debug:
        return False
    if not is_loopback_host(parsed.hostname or ""):
        return False
    path = parsed.path or ""
    return _DINGTALK_TEMP_IMAGE_PATH_RE.search(path) is not None


def _image_proxy_url_allowed(parsed: ParseResult) -> bool:
    domain = (parsed.hostname or "").lower()
    if domain in allowed_image_proxy_domains():
        return True
    return _dev_local_temp_image_url_allowed(parsed)


def _same_public_host(hostname: str) -> bool:
    """True when the image URL is this server's public host (not another MindGraph)."""
    host = (hostname or "").lower()
    if not host or is_loopback_host(host):
        return False
    external_base = normalize_external_base_url(os.getenv("EXTERNAL_BASE_URL", ""))
    if not external_base:
        return False
    return (urlparse(external_base).hostname or "").lower() == host


def _temp_image_name(path: str) -> str | None:
    """File name for a temp-image path. None when the path is not a temp image."""
    if "/api/temp_images/" in path:
        marker = "/api/temp_images/"
    elif "/temp_images/" in path:
        marker = "/temp_images/"
    else:
        return None
    name = path.split(marker, 1)[1]
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid URL")
    return name


def _signed_query(query: str) -> tuple[str | None, int | None]:
    parsed = parse_qs(query)
    sig_values = parsed.get("sig") or []
    exp_values = parsed.get("exp") or []
    sig = sig_values[0] if sig_values else None
    if not exp_values:
        return sig, None
    try:
        exp = int(exp_values[0])
    except ValueError:
        return sig, None
    return sig, exp


async def _local_temp_image(parsed: ParseResult) -> Response | None:
    """Read a temp PNG from this host's disk. Other hosts stay on HTTP."""
    host = (parsed.hostname or "").lower()
    if not _same_public_host(host) and not is_loopback_host(host):
        return None
    filename = _temp_image_name(parsed.path or "")
    if filename is None:
        return None
    sig, exp = _signed_query(parsed.query)
    try:
        return await serve_temp_image(filename, sig=sig, exp=exp)
    except HTTPException as exc:
        if exc.status_code == 404 and not _same_public_host(host):
            return None
        raise


@router.get("/proxy-image")
async def proxy_image(url: str = Query(..., description="The image URL to proxy")):
    """
    Proxy an external image to avoid CORS/CORB issues in the MindMate UI.

    Security:
    - Only allows images from whitelisted domains
    - A legacy mg host is fetched as www. Any other redirect is refused.
    - A temp image on this server is read from disk.
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

    fetch_url = rewrite_legacy_public_origin(upgrade_public_http_url(url))
    fetch_parsed = urlparse(fetch_url)
    local_image = await _local_temp_image(fetch_parsed)
    if local_image is not None:
        return local_image

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(fetch_url, follow_redirects=False)

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
        logger.warning(
            "Image proxy timed out host=%s path=%s",
            fetch_parsed.hostname,
            fetch_parsed.path,
        )
        raise HTTPException(status_code=504, detail="Timeout fetching image") from exc
    except httpx.RequestError as exc:
        logger.error("Error proxying image: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch image") from exc
