"""
Middleware: AbuseIPDB blacklist (Redis) + optional check score.
"""

from __future__ import annotations

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse

from services.infrastructure.security import abuseipdb_service
from services.infrastructure.security import ip_reputation_env_snapshot
from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)

_PATH_LOG_MAX = 120


def _ip_reputation_request_log_enabled() -> bool:
    """Per-request vetting logs; default off to avoid noisy production access logs."""
    raw = os.getenv("IP_REPUTATION_VERBOSE_LOG", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return False


def _path_for_log(path: str) -> str:
    if len(path) <= _PATH_LOG_MAX:
        return path
    return path[: _PATH_LOG_MAX - 3] + "..."


def _log_vetting_allowed(
    client_ip: str,
    method: str,
    path: str,
    *,
    had_blacklist_lookup: bool,
    check_enabled: bool,
    score: int | None,
    provenance: str | None,
    min_score: int,
) -> None:
    if not _ip_reputation_request_log_enabled():
        return
    parts = [f"ip={client_ip}", f"{method} {_path_for_log(path)}"]
    if had_blacklist_lookup:
        parts.append("shared_blacklist=miss")
    if check_enabled:
        if score is not None:
            parts.append(
                f"abuseipdb_score={score} ({provenance or '?'}) threshold={min_score}"
            )
        else:
            parts.append(f"abuseipdb_score=unavailable ({provenance or '?'})")
    else:
        parts.append("abuseipdb_live_check=off")
    logger.info("[IP reputation] Vetting allow: %s", ", ".join(parts))


def _should_skip_abuseipdb_path(path: str) -> bool:
    if path.startswith("/health"):
        return True
    if path.startswith("/static"):
        return True
    if path.startswith("/assets/"):
        return True
    # External webhooks (DingTalk MindBot, etc.): third-party egress must not be
    # blocked by shared-IP / datacenter AbuseIPDB scores.
    if path.startswith("/api/mindbot"):
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

    had_blacklist_lookup = ip_reputation_env_snapshot.blacklist_lookup_active()
    min_score = ip_reputation_env_snapshot.get_check_min_score_cached()
    check_enabled = ip_reputation_env_snapshot.abuseipdb_check_enabled_cached()
    score: int | None = None
    provenance: str | None = None

    if had_blacklist_lookup:
        if abuseipdb_service.is_ip_in_blacklist_set(client_ip):
            logger.warning(
                "[IP reputation] Blocked request from blacklisted IP %s (shared Redis set)",
                client_ip,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"},
            )

    if check_enabled:
        try:
            score, provenance = await abuseipdb_service.check_ip_score_cached_with_provenance(
                client_ip
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("[AbuseIPDB] check failed open: %s", exc)
            return await call_next(request)

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

    _log_vetting_allowed(
        client_ip,
        request.method,
        path,
        had_blacklist_lookup=had_blacklist_lookup,
        check_enabled=check_enabled,
        score=score,
        provenance=provenance,
        min_score=min_score,
    )

    return await call_next(request)
