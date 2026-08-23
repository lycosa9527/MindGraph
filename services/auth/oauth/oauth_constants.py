"""Constants for OAuth QR login flows."""

from __future__ import annotations

OAUTH_STATE_TTL_SECONDS = 600
OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_MODE_LOGIN = "login"
OAUTH_MODE_BIND = "bind"
OAUTH_ORG_UNSCOPED = 0

AUTH_ERROR_NOT_LINKED = "oauth_not_linked"
AUTH_ERROR_DISABLED = "oauth_disabled"
AUTH_ERROR_INVALID_STATE = "oauth_invalid_state"
AUTH_ERROR_EXCHANGE_FAILED = "oauth_exchange_failed"
AUTH_ERROR_CORP_MISMATCH = "oauth_corp_mismatch"
AUTH_ERROR_EXTERNAL_TAKEN = "oauth_external_taken"
AUTH_ERROR_ALREADY_BOUND = "oauth_already_bound"
AUTH_ERROR_INVALID_CODE = "oauth_invalid_code"
AUTH_ERROR_RATE_LIMITED = "oauth_rate_limited"
AUTH_ERROR_MISCONFIGURED = "oauth_misconfigured"

_USER_FACING_OAUTH_ERRORS = frozenset(
    {
        AUTH_ERROR_NOT_LINKED,
        AUTH_ERROR_DISABLED,
        AUTH_ERROR_INVALID_STATE,
        AUTH_ERROR_EXCHANGE_FAILED,
        AUTH_ERROR_CORP_MISMATCH,
        AUTH_ERROR_EXTERNAL_TAKEN,
        AUTH_ERROR_ALREADY_BOUND,
        AUTH_ERROR_INVALID_CODE,
        AUTH_ERROR_RATE_LIMITED,
        AUTH_ERROR_MISCONFIGURED,
    }
)

_CLIENT_CONFIG_ERRORS = frozenset(
    {
        "wechat_not_configured",
        "dingtalk_not_configured",
    }
)
_CLIENT_CODE_ERRORS = frozenset(
    {
        "code_required",
        "auth_code_required",
    }
)


def normalize_oauth_error_code(raw: str | ValueError) -> str:
    """Map internal/client errors to user-facing OAuth error codes."""
    code = str(raw) if not isinstance(raw, ValueError) else str(raw.args[0] if raw.args else raw)
    if code in _USER_FACING_OAUTH_ERRORS:
        return code
    if code in _CLIENT_CONFIG_ERRORS:
        return AUTH_ERROR_MISCONFIGURED
    if code in _CLIENT_CODE_ERRORS:
        return AUTH_ERROR_INVALID_CODE
    if code.endswith("_exchange_failed") or code.endswith("_userinfo_failed"):
        return AUTH_ERROR_EXCHANGE_FAILED
    return AUTH_ERROR_EXCHANGE_FAILED


DINGTALK_SCOPE_OPENID = "openid"

# Official WeChat Open Platform 网站应用 endpoints
WECHAT_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"

# Official DingTalk OAuth 2.0 v1.0 endpoints (not legacy oapi.dingtalk.com)
DINGTALK_USER_TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/userAccessToken"
DINGTALK_CONTACT_ME_URL = "https://api.dingtalk.com/v1.0/contact/users/me"
