"""
HttpOnly signed cookie: server has observed this browser from a mainland China IP.

Used with GeoIP so overseas email registration, email login, and email password
reset cannot be completed later only by using a VPN after a prior CN observation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from utils.auth import is_https
from utils.auth.jwt_secret import get_jwt_secret

logger = logging.getLogger(__name__)

GEO_CN_MAINLAND_COOKIE_NAME = "mg_geo_cn_mainland"
_GEO_CN_COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60
_GEO_CN_COOKIE_PAYLOAD = b"mindgraph:geo_cn_mainland:v1"


def _expected_cookie_value() -> str:
    secret = get_jwt_secret().encode("utf-8")
    return hmac.new(secret, _GEO_CN_COOKIE_PAYLOAD, hashlib.sha256).hexdigest()


def verify_geo_cn_mainland_cookie(cookie_value: Optional[str]) -> bool:
    """True if the cookie was set by this server for a prior CN-GeoIP observation."""
    if not cookie_value:
        return False
    try:
        expected = _expected_cookie_value()
    except (OSError, RuntimeError, ValueError):
        return False
    return hmac.compare_digest(cookie_value.encode("utf-8"), expected.encode("ascii"))


def set_geo_cn_mainland_cookie(response: Response, request: Request) -> None:
    """Stamp the browser after GeoIP resolves to mainland China (CN)."""
    try:
        value = _expected_cookie_value()
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Could not set geo CN mainland cookie: %s", exc)
        return
    response.set_cookie(
        key=GEO_CN_MAINLAND_COOKIE_NAME,
        value=value,
        max_age=_GEO_CN_COOKIE_MAX_AGE_SECONDS,
        path="/",
        samesite="lax",
        httponly=True,
        secure=is_https(request),
    )


def json_forbidden_cn_geo(
    detail: str,
    http_request: Request,
    stamp_cn_cookie: bool,
) -> JSONResponse:
    """
    403 when email registration, email login, or email reset is blocked by GeoIP/cookie.

    When ``stamp_cn_cookie`` is True, attaches the signed CN-observation cookie so a
    later VPN session is still blocked.
    """
    resp = JSONResponse(status_code=403, content={"detail": detail})
    if stamp_cn_cookie:
        set_geo_cn_mainland_cookie(resp, http_request)
    return resp
