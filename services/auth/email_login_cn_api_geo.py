"""
Apply the same email-login mainland CN GeoIP policy to authenticated API traffic.

Phone-only accounts (no email on file) are unchanged. Email accounts use
email_login_whitelisted_from_cn like browser email login routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse

from models.domain.auth import User
from models.domain.messages import Messages, get_request_language
from services.auth.geo_cn_mainland_cookie import json_forbidden_cn_geo
from services.auth.geoip_country import email_cn_geo_blocked
from services.auth.http_auth_token import extract_bearer_token, try_decode_access_token_payload
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import get_client_ip
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.auth.config import AUTH_MODE, EMAIL_LOGIN_CN_BLOCK_ENABLED
from utils.auth.user_tokens import validate_user_token


def _email_cn_geo_api_path_matches(request_path: str) -> bool:
    """Includes /api/auth (e.g. api-token) unlike VPN middleware."""
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


def _email_cn_geo_prereqs_ok(request: Request) -> bool:
    if not EMAIL_LOGIN_CN_BLOCK_ENABLED:
        return False
    if AUTH_MODE in ("demo", "bayi", "enterprise"):
        return False
    if request.headers.get("X-API-Key", "").strip():
        return False
    if not _email_cn_geo_api_path_matches(request.url.path):
        return False
    return True


async def _resolve_user_for_email_cn_geo(request: Request) -> Optional[User]:
    cached = getattr(request.state, AUTH_CONTEXT_USER_ATTR, None)
    if cached is not None:
        return cached
    payload = try_decode_access_token_payload(request)
    if payload:
        if payload.get("type") not in (None, "access"):
            return None
        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return None
        return await user_cache.get_by_id(user_id)

    token = extract_bearer_token(request)
    if not token or not token.startswith("mgat_"):
        return None
    account = (request.headers.get("X-MG-Account") or "").strip()
    if not account:
        return None
    return await validate_user_token(token, account, request=request)


async def maybe_enforce_email_login_cn_geo_api_async(request: Request) -> Optional[JSONResponse]:
    """
    Block overseas email accounts from CN IPs on API usage (JWT or mgat_), matching
    browser email login behavior.
    """
    if not _email_cn_geo_prereqs_ok(request):
        return None

    user = await _resolve_user_for_email_cn_geo(request)
    if user is None:
        return None

    if not (user.email or "").strip():
        return None

    lang = get_request_language(
        request.headers.get("X-Language"),
        request.headers.get("Accept-Language"),
    )
    must_deny, geo_msg_key, stamp_cn = email_cn_geo_blocked(
        get_client_ip(request),
        request,
        whitelisted_from_cn=getattr(user, "email_login_whitelisted_from_cn", False),
    )
    if not must_deny:
        return None

    detail = Messages.error(geo_msg_key, lang=lang)
    if geo_msg_key == "email_login_blocked_in_mainland_china":
        return json_forbidden_cn_geo(detail, request, stamp_cn)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": detail})
