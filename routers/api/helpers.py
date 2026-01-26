"""
helpers module.
"""
from typing import Optional
import base64
import hashlib
import hmac
import logging
import time

from fastapi import HTTPException, Request

from models.domain.auth import User
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth import get_jwt_secret


def get_rate_limit_identifier(current_user: Optional[User], request: Request) -> str:
    """
    Get identifier for rate limiting (user ID if authenticated, IP otherwise).

    Args:
        current_user: Current authenticated user (if any)
        request: FastAPI request object

    Returns:
        Rate limit identifier string
    """
    if current_user and hasattr(current_user, 'id'):
        return f"user:{current_user.id}"
    else:
        client_ip = request.client.host if request.client else 'unknown'
        return f"ip:{client_ip}"


async def check_endpoint_rate_limit(
    endpoint_name: str,
    identifier: str,
    max_requests: int = 30,
    window_seconds: int = 60
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

    is_allowed, count, error_msg = rate_limiter.check_and_record(
        category=f'api_{endpoint_name}',
        identifier=identifier,
        max_attempts=max_requests,
        window_seconds=window_seconds
    )

    if not is_allowed:
        logger.warning(
            "Rate limit exceeded for %s: %s (%s/%s requests)",
            endpoint_name, identifier, count, max_requests
        )
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. {error_msg}"
        )


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
    signature = hmac.new(
        get_jwt_secret().encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()

    # Base64 encode signature for URL safety
    signature_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')

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
    expected_signature = hmac.new(
        get_jwt_secret().encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()

    # Base64 encode for comparison
    expected_b64 = base64.urlsafe_b64encode(expected_signature).decode('utf-8').rstrip('=')

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_b64)
