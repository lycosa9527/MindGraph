"""
Captcha Endpoints
=================

CAPTCHA generation and verification endpoints:
- /captcha/generate - Generate captcha image
- verify_captcha_with_retry() - Helper function for captcha verification

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Tuple
import asyncio
import base64
import logging
import random
import uuid

from fastapi import APIRouter, HTTPException, Header, Request, Response, status

from models.domain.messages import Messages, get_request_language, Language
from services.auth.captcha_storage import get_captcha_storage
from services.redis.rate_limiting.redis_rate_limiter import check_captcha_rate_limit
from utils.auth import (
    CAPTCHA_SESSION_COOKIE_NAME,
    RATE_LIMIT_WINDOW_MINUTES,
    is_https
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy initialization - get captcha storage when needed (after Redis is initialized)
def _get_captcha_storage():
    """Get captcha storage instance (lazy initialization)."""
    return get_captcha_storage()

# Use closure pattern to avoid global statement and protected-access warnings
def _create_captcha_storage_ensurer():
    """Create a function that ensures captcha storage is initialized."""
    cache = None

    def _ensure_captcha_storage():
        """Ensure captcha storage is initialized."""
        nonlocal cache
        if cache is None:
            cache = get_captcha_storage()
        return cache

    return _ensure_captcha_storage

_ensure_captcha_storage = _create_captcha_storage_ensurer()


def _generate_captcha_svg(code: str) -> str:
    """
    Generate an SVG captcha image with distortion.

    This is the same implementation as MindLLMCross for consistent, readable captchas.

    Args:
        code: The captcha code string to render (4 characters)

    Returns:
        SVG string
    """
    width = 160
    height = 60

    # Random background color (light)
    bg_r = random.randint(230, 250)
    bg_g = random.randint(230, 250)
    bg_b = random.randint(230, 250)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="100%" height="100%" fill="rgb({bg_r},{bg_g},{bg_b})"/>',
    ]

    # Add noise lines
    for _ in range(5):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        color = f"rgb({random.randint(150,200)},{random.randint(150,200)},{random.randint(150,200)})"
        svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1"/>')

    # Add characters with random positioning and rotation
    fonts = ["Arial", "Verdana", "Georgia", "Times New Roman"]
    char_width = width // (len(code) + 1)

    for i, char in enumerate(code):
        x = char_width * (i + 0.5) + random.randint(-5, 5)
        y = height // 2 + random.randint(-5, 10)
        rotation = random.randint(-15, 15)
        font_size = random.randint(28, 36)
        font = random.choice(fonts)

        # Random dark color for text
        r = random.randint(20, 100)
        g = random.randint(20, 100)
        b = random.randint(20, 100)

        svg_parts.append(
            f'<text x="{x}" y="{y}" font-family="{font}" font-size="{font_size}" '
            f'font-weight="bold" fill="rgb({r},{g},{b})" '
            f'transform="rotate({rotation} {x} {y})">{char}</text>'
        )

    # Add noise dots
    for _ in range(30):
        cx, cy = random.randint(0, width), random.randint(0, height)
        r = random.randint(1, 2)
        color = f"rgb({random.randint(100,180)},{random.randint(100,180)},{random.randint(100,180)})"
        svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')

    svg_parts.append('</svg>')
    return ''.join(svg_parts)


@router.get("/captcha/generate")
async def generate_captcha(
    request: Request,
    response: Response,
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Generate SVG captcha image with readable letters (same as MindLLMCross)

    Features:
    - SVG format for crisp, scalable text
    - Font size 28-36px for excellent readability
    - Image dimensions: 160x60
    - Random fonts and colors per character
    - Noise lines and dots to prevent OCR bots
    - 100% self-hosted (China-compatible)
    - Rate limited: Max 30 requests per 15 minutes per session (browser cookie)

    Returns:
        {
            "captcha_id": "unique-session-id",
            "captcha_image": "data:image/svg+xml;base64,..."
        }
    """
    try:
        # Get or create session token for rate limiting
        session_token = request.cookies.get(CAPTCHA_SESSION_COOKIE_NAME)

        if not session_token:
            session_token = str(uuid.uuid4())
            logger.debug("New captcha session created: %s...", session_token[:8])

        # Rate limit by session token (Redis-backed, shared across workers)
        try:
            is_allowed, _ = check_captcha_rate_limit(session_token)
        except Exception as e:
            logger.error("Error checking captcha rate limit: %s", e, exc_info=True)
            # Fail open - allow captcha generation if rate limit check fails
            is_allowed = True

        if not is_allowed:
            logger.warning("Captcha rate limit exceeded for session: %s...", session_token[:8])
            accept_language = request.headers.get("Accept-Language", "")
            error_lang: Language = get_request_language(x_language, accept_language)
            error_msg = Messages.error("too_many_login_attempts", error_lang, RATE_LIMIT_WINDOW_MINUTES)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
    except HTTPException:
        # Re-raise HTTP exceptions (rate limit, etc.)
        raise
    except Exception as e:
        logger.error("Error in captcha generation (before generation): %s", e, exc_info=True)
        accept_language_err = request.headers.get("Accept-Language", "")
        error_lang_err: Language = get_request_language(x_language, accept_language_err)
        error_msg = Messages.error("captcha_generate_failed", error_lang_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) from e

    try:
        # Set session cookie (matches rate limit window duration)
        response.set_cookie(
            key=CAPTCHA_SESSION_COOKIE_NAME,
            value=session_token,
            httponly=True,
            secure=is_https(request),
            samesite="lax",
            max_age=RATE_LIMIT_WINDOW_MINUTES * 60  # 15 minutes
        )

        # Generate 4-character code
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        code = ''.join(random.choices(chars, k=4))

        # Generate SVG captcha image (same as MindLLMCross)
        svg = _generate_captcha_svg(code)
        img_base64 = base64.b64encode(svg.encode()).decode()

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Detect user language from headers
        accept_language_final = request.headers.get("Accept-Language", "")
        user_lang: Language = get_request_language(x_language, accept_language_final)

        # Store code with expiration (5 minutes)
        try:
            storage = _ensure_captcha_storage()
            success = storage.store(session_id, code, expires_in_seconds=300)
        except Exception as e:
            logger.error("Exception storing captcha %s: %s", session_id, e, exc_info=True)
            success = False

        if not success:
            logger.error("Failed to store captcha %s: Redis unavailable or storage failed", session_id)
            error_msg = Messages.error("captcha_generate_failed", user_lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )

        logger.debug("Generated captcha: %s for session: %s... (code: %s)", session_id, session_token[:8], code)

        return {
            "captcha_id": session_id,
            "captcha_image": f"data:image/svg+xml;base64,{img_base64}"
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error("Error generating captcha: %s", e, exc_info=True)
        accept_language_exc = request.headers.get("Accept-Language", "")
        error_lang_exc: Language = get_request_language(x_language, accept_language_exc)
        error_msg = Messages.error("captcha_generate_failed", error_lang_exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) from e


def verify_captcha(captcha_id: str, user_code: str) -> Tuple[bool, Optional[str]]:
    """
    Verify captcha code (synchronous wrapper for storage layer).

    Note: Verification is CASE-INSENSITIVE for better user experience.

    Returns:
        Tuple of (is_valid: bool, error_reason: Optional[str])
        error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
    Removes captcha after verification (one-time use)
    """
    storage = _ensure_captcha_storage()
    return storage.verify_and_remove(captcha_id, user_code)


async def verify_captcha_with_retry(
    captcha_id: str,
    user_code: str,
    max_endpoint_retries: int = 2
) -> Tuple[bool, Optional[str]]:
    """
    Verify captcha with endpoint-level retry for database lock errors.

    This provides an additional retry layer beyond storage-level retries (8 retries).
    Uses async sleep to avoid blocking the event loop.

    Args:
        captcha_id: Unique captcha identifier
        user_code: User-provided captcha code
        max_endpoint_retries: Maximum endpoint-level retries (default: 2)

    Returns:
        Tuple of (is_valid: bool, error_reason: Optional[str])
        error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
    """
    for attempt in range(max_endpoint_retries):
        captcha_valid, captcha_error = verify_captcha(captcha_id, user_code)

        if captcha_valid:
            return captcha_valid, captcha_error

        if captcha_error != "database_locked":
            return captcha_valid, captcha_error

        # Database lock error - retry with exponential backoff
        if attempt < max_endpoint_retries - 1:
            delay = 0.1 * (2 ** attempt)  # 0.1s, 0.2s
            logger.warning(
                "[Auth] Database lock in verify_captcha, "
                "endpoint retry %d/%d after %ss delay. "
                "Captcha ID: %s...",
                attempt + 1,
                max_endpoint_retries,
                delay,
                captcha_id[:8]
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                "[Auth] Database lock persists after %d endpoint retries. "
                "Captcha ID: %s...",
                max_endpoint_retries,
                captcha_id[:8]
            )
            return False, "database_locked"

    return False, "database_locked"

