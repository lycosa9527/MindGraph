"""
VPN / CN transition enforcement: Redis geo baseline + kick on non-CN login -> CN IP.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse

from models.domain.messages import Messages, get_request_language
from services.auth.email_login_cn_api_geo import maybe_enforce_email_login_cn_geo_api_async
from services.auth.geo_cn_mainland_cookie import json_forbidden_cn_geo
from services.auth.geoip_country import resolve_country_iso_from_request
from services.auth.http_auth_token import extract_bearer_token, try_decode_access_token_payload
from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.redis.session.redis_session_manager import get_refresh_token_manager, get_session_manager
from utils.auth import get_client_ip
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.auth.config import (
    AUTH_MODE,
    VPN_CN_KICKOUT_ALLOWLIST_USER_IDS,
    VPN_CN_KICKOUT_ENABLED,
)
from utils.auth.user_tokens import validate_user_token
from utils.cn_mobile import is_cn_mainland_mobile

logger = logging.getLogger(__name__)
_WS_CLOSE_REASON_MAX = 120


def should_kick_vpn_transition(login_cc: Optional[str], current_cc: Optional[str]) -> bool:
    if not login_cc or len(login_cc) != 2:
        return False
    if login_cc == "CN":
        return False
    if not current_cc or current_cc != "CN":
        return False
    return True


def _decode_redis_value(raw: object) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def _vpn_geo_path_matches(request_path: str) -> bool:
    if request_path.startswith("/api/auth"):
        return False
    if request_path.startswith("/api/frontend_log"):
        return False
    if request_path.startswith("/health"):
        return False
    if request_path.startswith("/api"):
        return True
    if request_path.startswith("/thinking_mode"):
        return True
    if request_path.startswith("/ws/"):
        return True
    return False


async def _refresh_geo_keys_ttl(redis: object, user_id: int, ttl: int) -> None:
    login_key = redis_keys.GEO_VPN_LOGIN_CC.format(user_id=user_id)
    last_ip_key = redis_keys.GEO_VPN_LAST_IP.format(user_id=user_id)
    async with redis.pipeline(transaction=False) as pipe:
        pipe.expire(login_key, ttl)
        pipe.expire(last_ip_key, ttl)
        await pipe.execute()


async def record_vpn_login_geo(user_id: int, request: Request) -> None:
    if not VPN_CN_KICKOUT_ENABLED:
        return
    if AUTH_MODE in ("demo", "bayi", "enterprise"):
        return
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    client_ip = get_client_ip(request)
    country = resolve_country_iso_from_request(request)
    login_val = country if country else ""
    ttl = redis_keys.TTL_GEO_VPN
    login_key = redis_keys.GEO_VPN_LOGIN_CC.format(user_id=user_id)
    last_ip_key = redis_keys.GEO_VPN_LAST_IP.format(user_id=user_id)
    async with redis.pipeline(transaction=False) as pipe:
        pipe.setex(login_key, ttl, login_val)
        pipe.setex(last_ip_key, ttl, client_ip)
        await pipe.execute()


async def record_vpn_refresh_last_ip(user_id: int, request: Request) -> None:
    if not VPN_CN_KICKOUT_ENABLED:
        return
    if AUTH_MODE in ("demo", "bayi", "enterprise"):
        return
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    client_ip = get_client_ip(request)
    ttl = redis_keys.TTL_GEO_VPN
    login_key = redis_keys.GEO_VPN_LOGIN_CC.format(user_id=user_id)
    last_ip_key = redis_keys.GEO_VPN_LAST_IP.format(user_id=user_id)
    async with redis.pipeline(transaction=False) as pipe:
        pipe.setex(last_ip_key, ttl, client_ip)
        pipe.expire(login_key, ttl)
        pipe.expire(last_ip_key, ttl)
        await pipe.execute()


def _vpn_geo_prereqs_ok(request: Request) -> bool:
    if not VPN_CN_KICKOUT_ENABLED:
        return False
    if AUTH_MODE in ("demo", "bayi", "enterprise"):
        return False
    if request.headers.get("X-API-Key", "").strip():
        return False
    if not _vpn_geo_path_matches(request.url.path):
        return False
    return True


async def maybe_enforce_vpn_cn_geo_for_user(
    request: Request,
    user_id: int,
    phone_str: Optional[str],
) -> Optional[JSONResponse]:
    """
    Apply VPN/CN transition rules for a known user (browser JWT or OpenClaw mgat_).
    """
    if user_id in VPN_CN_KICKOUT_ALLOWLIST_USER_IDS:
        return None

    if is_cn_mainland_mobile(phone_str):
        return None

    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None

    client_ip = get_client_ip(request)
    ttl = redis_keys.TTL_GEO_VPN
    login_key = redis_keys.GEO_VPN_LOGIN_CC.format(user_id=user_id)
    last_ip_key = redis_keys.GEO_VPN_LAST_IP.format(user_id=user_id)

    async with redis.pipeline(transaction=False) as pipe:
        pipe.get(login_key)
        pipe.get(last_ip_key)
        login_raw, last_ip_raw = await pipe.execute()
    login_cc = _decode_redis_value(login_raw)
    last_ip = _decode_redis_value(last_ip_raw)

    if login_raw is None:
        current = resolve_country_iso_from_request(request)
        login_val = current if current else ""
        async with redis.pipeline(transaction=False) as write_pipe:
            write_pipe.setex(login_key, ttl, login_val)
            write_pipe.setex(last_ip_key, ttl, client_ip)
            await write_pipe.execute()
        return None

    if last_ip == client_ip:
        async with redis.pipeline(transaction=False) as ttl_pipe:
            ttl_pipe.expire(login_key, ttl)
            ttl_pipe.expire(last_ip_key, ttl)
            await ttl_pipe.execute()
        return None

    current_cc = resolve_country_iso_from_request(request)
    await redis.setex(last_ip_key, ttl, client_ip)

    if should_kick_vpn_transition(login_cc, current_cc):
        await get_session_manager().invalidate_user_sessions(user_id, ip_address=client_ip)
        revoked = await get_refresh_token_manager().revoke_all_refresh_tokens(
            user_id,
            reason="vpn_cn_geo",
        )
        logger.info(
            "[VPNGeo] Kick user_id=%s ip=%s login_cc=%s current_cc=%s refresh_revoked=%s",
            user_id,
            client_ip,
            login_cc,
            current_cc,
            revoked,
        )
        lang = get_request_language(
            request.headers.get("X-Language"),
            request.headers.get("Accept-Language"),
        )
        detail = Messages.error("vpn_cn_session_terminated", lang=lang)
        return json_forbidden_cn_geo(detail, request, stamp_cn_cookie=True)

    return None


async def maybe_enforce_vpn_cn_geo(request: Request) -> Optional[JSONResponse]:
    if not _vpn_geo_prereqs_ok(request):
        return None

    payload = try_decode_access_token_payload(request)
    if not payload:
        return None
    if payload.get("type") not in (None, "access"):
        return None

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    raw_phone = payload.get("phone")
    phone_str = raw_phone if isinstance(raw_phone, str) else None
    return await maybe_enforce_vpn_cn_geo_for_user(request, user_id, phone_str)


async def maybe_enforce_vpn_cn_geo_async(request: Request) -> Optional[JSONResponse]:
    """
    Email-login CN GeoIP on API (JWT/mgat_), then VPN/CN transition (JWT/mgat_).
    """
    blocked = await maybe_enforce_email_login_cn_geo_api_async(request)
    if blocked is not None:
        return blocked

    if not _vpn_geo_prereqs_ok(request):
        return None

    state_user = getattr(request.state, AUTH_CONTEXT_USER_ATTR, None)
    if state_user is not None:
        phone_str = state_user.phone if isinstance(state_user.phone, str) else None
        return await maybe_enforce_vpn_cn_geo_for_user(request, state_user.id, phone_str)

    payload = try_decode_access_token_payload(request)
    if payload:
        if payload.get("type") not in (None, "access"):
            return None
        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return None
        raw_phone = payload.get("phone")
        phone_str = raw_phone if isinstance(raw_phone, str) else None
        return await maybe_enforce_vpn_cn_geo_for_user(request, user_id, phone_str)

    token = extract_bearer_token(request)
    if not token or not token.startswith("mgat_"):
        return None
    account = (request.headers.get("X-MG-Account") or "").strip()
    if not account:
        return None

    user = await validate_user_token(token, account, request=request)
    return await maybe_enforce_vpn_cn_geo_for_user(request, user.id, user.phone)


def _close_reason_from_geo_json_response(resp: JSONResponse) -> Optional[str]:
    body = getattr(resp, "body", None)
    if body is None:
        return None
    raw = bytes(body) if not isinstance(body, (bytes, bytearray)) else body
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        return None
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
    return None


async def maybe_close_websocket_for_vpn_cn_geo(websocket: WebSocket) -> bool:
    """
    Run the same VPN/CN policy as HTTP middleware on a WebSocket scope.

    If the connection must be blocked, invalidates sessions (and refresh tokens) and
    closes the socket. Call after successful WebSocket auth, before or after accept().

    Returns:
        True if the socket was closed (caller should return).
    """
    # WebSocket is an HTTPConnection subclass with the same headers/url/state interface
    # as Request. Constructing Request(websocket.scope) fails because Request.__init__
    # asserts scope["type"] == "http", but WebSocket scopes carry type="websocket".
    resp = await maybe_enforce_vpn_cn_geo_async(websocket)  # type: ignore[arg-type]
    if resp is None:
        return False
    lang = get_request_language(
        websocket.headers.get("X-Language"),
        websocket.headers.get("Accept-Language"),
    )
    reason = _close_reason_from_geo_json_response(resp)
    if not reason:
        reason = Messages.error("vpn_cn_session_terminated", lang=lang)
    if len(reason) > _WS_CLOSE_REASON_MAX:
        reason = reason[:_WS_CLOSE_REASON_MAX]
    await websocket.close(code=4403, reason=reason)
    return True
