"""Kick-notice helpers for /refresh and /session-status.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from fastapi import HTTPException, Request, Response, status

from routers.auth.helpers import clear_auth_cookies
from services.redis.session.redis_session_manager import RedisSessionManager
from services.redis.session.session_store_lua import FIFO_KICK_REASON

logger = logging.getLogger(__name__)

KICK_DETAIL_MAX_DEVICES = "Session ended: maximum device limit exceeded"
KICK_DETAIL_DEVICE = "Session ended: signed out from another device"
MANUAL_KICK_REASON = "device_kick"


def kick_http_detail(reason: str) -> str:
    """User-facing 401 / session-status copy for a kick reason."""
    if reason == MANUAL_KICK_REASON:
        return KICK_DETAIL_DEVICE
    return KICK_DETAIL_MAX_DEVICES


def access_token_hash(access_token: str) -> str:
    """SHA256 hex of the raw access JWT."""
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


async def find_session_kick(
    user_id: int,
    access_token: Optional[str],
    device_hash: str,
    session_manager: RedisSessionManager,
) -> Optional[dict[str, str]]:
    """
    Return kick metadata when this device or access token was evicted.

    The per-device fence is authoritative for in-flight /refresh: Lua writes
    it in the same EVAL as access eviction, before Python revokes refresh.
    """
    if access_token:
        notice = await session_manager.check_invalidation_notification(
            user_id,
            access_token_hash(access_token),
        )
        if notice:
            return {
                "reason": str(notice.get("reason") or FIFO_KICK_REASON),
                "ip_address": str(notice.get("ip_address") or "unknown"),
                "timestamp": str(notice.get("timestamp") or ""),
            }
    if device_hash:
        reason = await session_manager.get_device_eviction_reason(user_id, device_hash)
        if reason:
            return {
                "reason": reason,
                "ip_address": "unknown",
                "timestamp": "",
            }
    return None


def raise_refresh_kicked(
    request: Request,
    response: Response,
    user_id: int,
    client_ip: str,
    notice: dict[str, str],
) -> None:
    """Clear cookies and 401 a kicked refresh attempt."""
    kick_reason = notice.get("reason") or FIFO_KICK_REASON
    logger.info(
        "[TokenAudit] Refresh FAILED - session kicked (%s): user=%s, ip=%s",
        kick_reason,
        user_id,
        client_ip,
    )
    clear_auth_cookies(response, request)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=kick_http_detail(kick_reason),
    )
