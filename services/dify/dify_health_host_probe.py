"""
Host-level Dify reachability probe for shared-base-URL failover health checks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional, Sequence, Tuple

from services.dify.dify_health_logging import LOG_PREFIX
from services.mindbot.dify.service_health import check_dify_app_api_reachable

logger = logging.getLogger(__name__)

_AUTH_HTTP_STATUSES = frozenset({401, 403})

_ProbeOutcome = Tuple[bool, Optional[int], Optional[str]]


def is_dify_auth_failure(http_status: Optional[int], err: Optional[str]) -> bool:
    """True when the host answered but rejected the app key."""
    if http_status in _AUTH_HTTP_STATUSES:
        return True
    return err in {"http_401", "http_403"}


def classify_host_probe_outcome(outcomes: Sequence[_ProbeOutcome]) -> _ProbeOutcome:
    """
    Collapse per-key probe attempts into one host verdict.

    - Any HTTP 200 → host online.
    - Only auth failures (401/403) → host online (reachable; bad keys are not outages).
    - Timeout / connection / non-auth HTTP errors → host offline.
    """
    if not outcomes:
        return False, None, "api_key_not_configured"

    last_auth: Optional[_ProbeOutcome] = None
    for online, http_status, err in outcomes:
        if online:
            return True, http_status, err
        if is_dify_auth_failure(http_status, err):
            last_auth = (online, http_status, err)
            continue
        return False, http_status, err

    if last_auth is not None:
        _, http_status, err = last_auth
        return True, http_status, err or "auth_only_host_reachable"
    return False, None, "probe_failed"


async def check_dify_host_reachable(
    base_url: str,
    api_keys: Iterable[str],
    *,
    timeout_s: float = 10.0,
) -> _ProbeOutcome:
    """
    Probe one Dify base URL using candidate app keys.

    Retries on auth failure with the next key. Stops early on success or on a
    non-auth failure (timeout, connection error, 5xx, etc.).
    """
    attempts: list[_ProbeOutcome] = []
    unique_keys: list[str] = []
    seen: set[str] = set()
    for raw_key in api_keys:
        key = (raw_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_keys.append(key)

    if not unique_keys:
        return False, None, "api_key_not_configured"

    for index, api_key in enumerate(unique_keys):
        outcome = await check_dify_app_api_reachable(
            base_url,
            api_key,
            timeout_s=timeout_s,
        )
        attempts.append(outcome)
        online, http_status, err = outcome
        if online:
            if index > 0:
                logger.info(
                    "%s Host %s reachable with fallback app key (attempt %s/%s).",
                    LOG_PREFIX,
                    (base_url or "").strip().rstrip("/"),
                    index + 1,
                    len(unique_keys),
                )
            return outcome
        if is_dify_auth_failure(http_status, err):
            logger.debug(
                "%s Host %s rejected app key (%s); trying next candidate if any.",
                LOG_PREFIX,
                (base_url or "").strip().rstrip("/"),
                err or http_status,
            )
            continue
        return outcome

    verdict = classify_host_probe_outcome(attempts)
    if verdict[0]:
        logger.warning(
            "%s Host %s answered but every candidate app key failed auth "
            "(%s key(s)); treating host as online for failover.",
            LOG_PREFIX,
            (base_url or "").strip().rstrip("/"),
            len(unique_keys),
        )
    return verdict
