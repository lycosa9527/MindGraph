"""
helpers module.
"""

from datetime import datetime, timezone
from typing import Optional
import base64
import hashlib
import hmac
import logging
import os
import time

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth import get_jwt_secret

_logger = logging.getLogger(__name__)


def strip_leading_http_schemes(value: str) -> str:
    """
    Remove leading http:// and https:// prefixes, repeatedly.

    Some reverse proxies send a full URL in X-Forwarded-Host; the Host part must
    not include a scheme, since we build scheme separately from X-Forwarded-Proto.
    """
    result = (value or "").strip()
    while True:
        lower = result.lower()
        if lower.startswith("https://"):
            result = result[8:]
        elif lower.startswith("http://"):
            result = result[7:]
        else:
            break
    return result


def collapse_double_scheme_base_url(value: str) -> str:
    """Fix EXTERNAL_BASE_URL values like http://https://host when mis-set."""
    result = (value or "").strip()
    for _ in range(3):
        lower = result.lower()
        if lower.startswith("http://https://"):
            result = result[7:]
        elif lower.startswith("https://http://"):
            result = result[8:]
        else:
            break
    return result.rstrip("/")


def _strip_redundant_trailing_api_path(base: str) -> str:
    """
    If EXTERNAL_BASE_URL is set to .../api (mount path duplicated in env), drop the final
    /api so we do not build .../api/api/temp_images/...
    """
    s = (base or "").strip().rstrip("/")
    if len(s) >= 4 and s[-4:].lower() == "/api":
        return s[:-4].rstrip("/")
    return s


def normalize_external_base_url(value: str) -> str:
    """
    Canonical public site base from EXTERNAL_BASE_URL: fix double-scheme typos, trim slashes,
    drop a mistaken trailing /api, require http(s) scheme (otherwise return empty).
    """
    collapsed = collapse_double_scheme_base_url(value)
    if not collapsed:
        return ""
    no_dup_api = _strip_redundant_trailing_api_path(collapsed)
    low = no_dup_api.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return ""
    return no_dup_api


def _signed_path_for_public_url(signed_path: str) -> str:
    """Avoid double slashes in the final URL; signed segment must not be absolute."""
    p = (signed_path or "").strip()
    return p.lstrip("/")


def _host_has_traditional_port(authority: str) -> bool:
    """
    True if authority looks like hostname:port (one colon, port 1-65535).

    Avoids appending :PORT from env when EXTERNAL_HOST is already
    e.g. main.example.com:9527.
    """
    if not authority or authority.count(":") != 1 or authority.startswith("["):
        return False
    _host, port_s = authority.rsplit(":", 1)
    if not _host or not port_s.isdigit():
        return False
    p = int(port_s)
    return 1 <= p <= 65535


def _is_local_loopback_host(host: str) -> bool:
    """True for typical local dev hostnames; those links need the Uvicorn bind port."""
    b = (host or "").lower().strip()
    if b in ("localhost", "127.0.0.1", "::1"):
        return True
    if b.count(".") == 3 and b.startswith("127."):
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in b.split("."))
    return False


def _authority_for_public_temp_url(authority: str) -> str:
    """
    Build host[:port] for public temp-image URLs when not using X-Forwarded-* or EXTERNAL_BASE_URL.

    ``os.environ["PORT"]`` is the process bind port (e.g. 9527), not the public URL port. Behind a
    reverse proxy, browsers use 443/80; public links must not add :9527. Localhost links still
    need the bind port to reach the API.

    Set ``EXTERNAL_PUBLIC_PORT`` to force a non-default port on a public hostname (rare; prefer
    ``EXTERNAL_BASE_URL`` for full control).
    """
    auth = (authority or "").strip()
    if not auth:
        return f"localhost:{os.getenv('PORT', '9527')}"
    if _host_has_traditional_port(auth):
        return auth
    if _is_local_loopback_host(auth):
        return f"{auth}:{os.getenv('PORT', '9527')}"
    public_port = (os.getenv("EXTERNAL_PUBLIC_PORT") or "").strip()
    if public_port.isdigit() and 1 <= int(public_port) <= 65535:
        return f"{auth}:{int(public_port)}"
    return auth


def build_public_temp_image_url(request: Request, signed_path: str) -> str:
    """
    Public URL for /api/temp_images (signed path).

    Order: EXTERNAL_BASE_URL, then X-Forwarded-Proto/Host, then EXTERNAL_HOST (see
    _authority_for_public_temp_url: public hostnames omit bind PORT unless EXTERNAL_PUBLIC_PORT).
    """
    path_seg = _signed_path_for_public_url(signed_path)

    external_base = normalize_external_base_url(os.getenv("EXTERNAL_BASE_URL", ""))
    if external_base:
        return f"{external_base}/api/temp_images/{path_seg}"

    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").strip()
    forwarded_host_raw = (request.headers.get("X-Forwarded-Host") or "").strip()
    if forwarded_proto and forwarded_host_raw:
        host_only = strip_leading_http_schemes(forwarded_host_raw).strip().rstrip("/")
        if host_only:
            return f"{forwarded_proto}://{host_only}/api/temp_images/{path_seg}"

    protocol = request.url.scheme
    raw_host = strip_leading_http_schemes(os.getenv("EXTERNAL_HOST", "localhost") or "localhost")
    if not raw_host:
        raw_host = "localhost"
    public_authority = _authority_for_public_temp_url(raw_host)
    return f"{protocol}://{public_authority}/api/temp_images/{path_seg}"


async def log_diagram_edit(user: User, db: AsyncSession, count: int = 1) -> None:
    """Log diagram_edit events to UserActivityLog for teacher usage tracking."""
    if getattr(user, "role", None) != "user" or count < 1:
        return
    try:
        now = datetime.now(timezone.utc)
        for _ in range(min(count, 1000)):
            log_entry = UserActivityLog(
                user_id=user.id,
                activity_type="diagram_edit",
                created_at=now,
            )
            db.add(log_entry)
        await db.commit()
    except Exception as exc:
        _logger.debug("Failed to log diagram_edit: %s", exc)
        try:
            await db.rollback()
        except Exception as rollback_exc:
            _logger.debug("Rollback after activity log failure: %s", rollback_exc)


def get_rate_limit_identifier(current_user: Optional[User], request: Request) -> str:
    """
    Get identifier for rate limiting (user ID if authenticated, IP otherwise).

    Args:
        current_user: Current authenticated user (if any)
        request: FastAPI request object

    Returns:
        Rate limit identifier string
    """
    if current_user and hasattr(current_user, "id"):
        return f"user:{current_user.id}"
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


async def check_endpoint_rate_limit(
    endpoint_name: str,
    identifier: str,
    max_requests: int = 30,
    window_seconds: int = 60,
) -> None:
    """
    Check rate limit for expensive endpoints.

    Args:
        endpoint_name: Name of the endpoint (for logging)
        identifier: Rate limit identifier (user ID or IP)
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Raises:
        HTTPException: If rate limit exceeded
    """
    logger = logging.getLogger(__name__)
    rate_limiter = RedisRateLimiter()

    is_allowed, count, error_msg = await rate_limiter.check_and_record(
        category=f"api_{endpoint_name}",
        identifier=identifier,
        max_attempts=max_requests,
        window_seconds=window_seconds,
    )

    if not is_allowed:
        logger.warning(
            "Rate limit exceeded for %s: %s (%s/%s requests)",
            endpoint_name,
            identifier,
            count,
            max_requests,
        )
        raise HTTPException(status_code=429, detail=f"Too many requests. {error_msg}")


def generate_signed_url(filename: str, expiration_seconds: int = 86400) -> str:
    """
    Generate a signed URL for temporary image access.

    Args:
        filename: Image filename
        expiration_seconds: URL expiration time in seconds (default 24 hours)

    Returns:
        Signed URL with signature and expiration timestamp
    """
    expiration = int(time.time()) + expiration_seconds
    message = f"{filename}:{expiration}"

    # Generate HMAC signature
    signature = hmac.new(get_jwt_secret().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()

    # Base64 encode signature for URL safety
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{filename}?sig={signature_b64}&exp={expiration}"


def verify_signed_url(filename: str, signature: str, expiration: int) -> bool:
    """
    Verify a signed URL for temporary image access.

    Args:
        filename: Image filename
        signature: URL signature
        expiration: Expiration timestamp

    Returns:
        True if signature is valid and not expired, False otherwise
    """
    # Check expiration
    if int(time.time()) > expiration:
        return False

    # Reconstruct message
    message = f"{filename}:{expiration}"

    # Generate expected signature
    expected_signature = hmac.new(get_jwt_secret().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()

    # Base64 encode for comparison
    expected_b64 = base64.urlsafe_b64encode(expected_signature).decode("utf-8").rstrip("=")

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_b64)
