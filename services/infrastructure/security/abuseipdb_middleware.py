"""
Middleware: AbuseIPDB blacklist (Redis) + optional check score.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from services.infrastructure.security import abuseipdb_service
from services.infrastructure.security import ip_reputation_env_snapshot
from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)


def _should_skip_abuseipdb_path(path: str) -> bool:
    if path.startswith("/health"):
        return True
    if path.startswith("/static"):
        return True
    if path.startswith("/assets/"):
        return True
    if path in ("/favicon.ico", "/robots.txt"):
        return True
    return False


async def abuseipdb_middleware(request: Request, call_next):
    """Block high-risk IPs using daily blacklist and/or check API (fail open on errors)."""
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if _should_skip_abuseipdb_path(path):
        return await call_next(request)

    if ip_reputation_env_snapshot.should_skip_ip_reputation_middleware():
        return await call_next(request)

    client_ip = get_client_ip(request)
    if abuseipdb_service.client_ip_is_skipped_for_abuseipdb(client_ip):
        return await call_next(request)

    if ip_reputation_env_snapshot.blacklist_lookup_active():
        if abuseipdb_service.is_ip_in_blacklist_set(client_ip):
            logger.warning(
                "[IP reputation] Blocked request from blacklisted IP %s",
                client_ip,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"},
            )

    if ip_reputation_env_snapshot.abuseipdb_check_enabled_cached():
        try:
            score = await abuseipdb_service.check_ip_score_cached(client_ip)
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("[AbuseIPDB] check failed open: %s", exc)
            return await call_next(request)

        min_score = ip_reputation_env_snapshot.get_check_min_score_cached()
        if score is not None and score >= min_score:
            logger.warning(
                "[AbuseIPDB] Blocked request from IP %s (score=%s >= %s)",
                client_ip,
                score,
                min_score,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"},
            )

    return await call_next(request)
