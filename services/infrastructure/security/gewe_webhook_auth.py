"""
Gewe webhook request authentication.

When ``FEATURE_GEWE`` is enabled, production deployments must set
``GEWE_WEBHOOK_SECRET``. Optional ``GEWE_WEBHOOK_ALLOWED_IPS`` restricts
source IPs (comma-separated). When the allowlist is empty, any IP may call
the webhook if the HMAC signature is valid.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import HTTPException, Request, status

from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)


def _allowed_ips() -> set[str]:
    raw = os.getenv("GEWE_WEBHOOK_ALLOWED_IPS", "").strip()
    if not raw:
        return set()
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _webhook_secret() -> str:
    return os.getenv("GEWE_WEBHOOK_SECRET", "").strip()


def verify_gewe_webhook_request(request: Request, raw_body: bytes) -> None:
    """Validate webhook IP allowlist (when configured) and HMAC signature."""
    allowed = _allowed_ips()
    if allowed:
        client_ip = get_client_ip(request)
        if client_ip not in allowed:
            logger.warning("Gewe webhook rejected: IP %s not in allowlist", client_ip)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Webhook source IP not allowed",
            )

    secret = _webhook_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gewe webhook secret is not configured (set GEWE_WEBHOOK_SECRET)",
        )

    signature = request.headers.get("X-Gewe-Signature") or request.headers.get("X-Webhook-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(provided, expected):
        logger.warning("Gewe webhook rejected: invalid signature from %s", get_client_ip(request))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
