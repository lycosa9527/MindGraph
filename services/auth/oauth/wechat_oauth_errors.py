"""Map official WeChat Open Platform errcodes for website OAuth login.

Catalog: https://developers.weixin.qq.com/doc/oplatform/developers/errCode/
Only the codes returned by sns/oauth2/access_token and sns/userinfo are mapped.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.auth.oauth.oauth_constants import (
    AUTH_ERROR_EXCHANGE_FAILED,
    AUTH_ERROR_INVALID_CODE,
    AUTH_ERROR_MISCONFIGURED,
    AUTH_ERROR_RATE_LIMITED,
)

logger = logging.getLogger(__name__)

# Official 全局错误码 (公共 + 通用) that website QR login actually returns.
WECHAT_ERR_SYSTEM = -1
WECHAT_ERR_INVALID_CREDENTIAL = 40001
WECHAT_ERR_INVALID_OPENID = 40003
WECHAT_ERR_INVALID_APPID = 40013
WECHAT_ERR_INVALID_ACCESS_TOKEN = 40014
WECHAT_ERR_INVALID_CODE = 40029
WECHAT_ERR_INVALID_REFRESH_TOKEN = 40030
WECHAT_ERR_INVALID_APPSECRET = 40125
WECHAT_ERR_CODE_BEEN_USED = 40163
WECHAT_ERR_ACCESS_TOKEN_MISSING = 41001
WECHAT_ERR_APPID_MISSING = 41002
WECHAT_ERR_APPSECRET_MISSING = 41004
WECHAT_ERR_CODE_MISSING = 41008
WECHAT_ERR_ACCESS_TOKEN_EXPIRED = 42001
WECHAT_ERR_DAILY_QUOTA = 45009
WECHAT_ERR_MINUTE_QUOTA = 45011

_INVALID_CODE_ERRS = frozenset(
    {
        WECHAT_ERR_INVALID_CODE,
        WECHAT_ERR_CODE_BEEN_USED,
        WECHAT_ERR_CODE_MISSING,
        WECHAT_ERR_INVALID_REFRESH_TOKEN,
    }
)
_RATE_LIMIT_ERRS = frozenset(
    {
        WECHAT_ERR_SYSTEM,
        WECHAT_ERR_DAILY_QUOTA,
        WECHAT_ERR_MINUTE_QUOTA,
    }
)
_MISCONFIGURED_ERRS = frozenset(
    {
        WECHAT_ERR_INVALID_APPID,
        WECHAT_ERR_INVALID_APPSECRET,
        WECHAT_ERR_APPID_MISSING,
        WECHAT_ERR_APPSECRET_MISSING,
    }
)
_TOKEN_ERRS = frozenset(
    {
        WECHAT_ERR_INVALID_CREDENTIAL,
        WECHAT_ERR_INVALID_OPENID,
        WECHAT_ERR_INVALID_ACCESS_TOKEN,
        WECHAT_ERR_ACCESS_TOKEN_MISSING,
        WECHAT_ERR_ACCESS_TOKEN_EXPIRED,
    }
)


def parse_wechat_errcode(data: dict[str, Any]) -> Optional[int]:
    """Return WeChat errcode when the payload is an error (not 0/ok)."""
    raw = data.get("errcode")
    if raw is None or raw == "" or raw is False:
        return None
    try:
        code = int(raw)
    except (TypeError, ValueError):
        return None
    if code == 0:
        return None
    return code


def map_wechat_errcode(errcode: Optional[int]) -> str:
    """Map an official WeChat errcode to a stable oauth_* toast code."""
    if errcode is None:
        return AUTH_ERROR_EXCHANGE_FAILED
    if errcode in _INVALID_CODE_ERRS:
        return AUTH_ERROR_INVALID_CODE
    if errcode in _RATE_LIMIT_ERRS:
        return AUTH_ERROR_RATE_LIMITED
    if errcode in _MISCONFIGURED_ERRS:
        return AUTH_ERROR_MISCONFIGURED
    if errcode in _TOKEN_ERRS:
        return AUTH_ERROR_EXCHANGE_FAILED
    return AUTH_ERROR_EXCHANGE_FAILED


def log_wechat_api_error(*, api: str, data: dict[str, Any]) -> str:
    """Log official errcode/errmsg/rid and return the user-facing oauth_* code."""
    errcode = parse_wechat_errcode(data)
    errmsg = str(data.get("errmsg") or "").strip()
    rid = str(data.get("rid") or "").strip()
    oauth_code = map_wechat_errcode(errcode)
    logger.warning(
        "WeChat %s failed errcode=%s errmsg=%s rid=%s oauth=%s",
        api,
        errcode if errcode is not None else "missing",
        errmsg or "-",
        rid or "-",
        oauth_code,
    )
    return oauth_code
