"""
Image Proxy API Router
======================

API endpoint to proxy external images to avoid CORS issues.
Used by ShareExportModal for PNG export when AI responses contain images.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from urllib.parse import urlparse
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
import httpx



logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

# Allowed domains for image proxying (security whitelist)
ALLOWED_DOMAINS = [
    "mg.mindspringedu.com",
    "localhost",
    "127.0.0.1",
]


@router.get('/proxy-image')
async def proxy_image(url: str = Query(..., description="The image URL to proxy")):
    """
    Proxy an external image to avoid CORS issues.

    This endpoint fetches an image from an external URL and returns it,
    allowing the frontend to use it in html-to-image without CORS errors.

    Security:
    - Only allows images from whitelisted domains
    - Only allows image content types
    - Limits response size to 10MB
    """
    # Validate URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid URL") from exc

    # Security: Check domain whitelist
    domain = parsed.netloc.split(':')[0]  # Remove port if present
    if domain not in ALLOWED_DOMAINS:
        logger.warning("Image proxy blocked for non-whitelisted domain: %s", domain)
        raise HTTPException(status_code=403, detail="Domain not allowed")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch image"
                )

            # Validate content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail="URL does not point to an image"
                )

            # Limit size to 10MB
            content_length = len(response.content)
            if content_length > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="Image too large (max 10MB)"
                )

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    'Cache-Control': 'public, max-age=3600',
                    'X-Content-Type-Options': 'nosniff'
                }
            )

    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timeout fetching image") from exc
    except httpx.RequestError as exc:
        logger.error("Error proxying image: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch image") from exc
