"""Constants for OAuth QR login flows."""

from __future__ import annotations

OAUTH_STATE_TTL_SECONDS = 600
OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_MODE_LOGIN = "login"
OAUTH_MODE_BIND = "bind"

AUTH_ERROR_NOT_LINKED = "oauth_not_linked"
AUTH_ERROR_DISABLED = "oauth_disabled"
AUTH_ERROR_INVALID_STATE = "oauth_invalid_state"
AUTH_ERROR_EXCHANGE_FAILED = "oauth_exchange_failed"
AUTH_ERROR_CORP_MISMATCH = "oauth_corp_mismatch"
AUTH_ERROR_EXTERNAL_TAKEN = "oauth_external_taken"

_USER_FACING_OAUTH_ERRORS = frozenset(
    {
        AUTH_ERROR_NOT_LINKED,
        AUTH_ERROR_DISABLED,
        AUTH_ERROR_INVALID_STATE,
        AUTH_ERROR_EXCHANGE_FAILED,
        AUTH_ERROR_CORP_MISMATCH,
        AUTH_ERROR_EXTERNAL_TAKEN,
    }
)


def normalize_oauth_error_code(raw: str | ValueError) -> str:
    """Map internal/client errors to user-facing OAuth error codes."""
    code = str(raw) if not isinstance(raw, ValueError) else str(raw.args[0] if raw.args else raw)
    if code in _USER_FACING_OAUTH_ERRORS:
        return code
    if code.endswith("_exchange_failed") or code.endswith("_userinfo_failed"):
        return AUTH_ERROR_EXCHANGE_FAILED
    if code in {"wechat_not_configured", "dingtalk_not_configured", "code_required", "auth_code_required"}:
        return AUTH_ERROR_EXCHANGE_FAILED
    return AUTH_ERROR_EXCHANGE_FAILED


DINGTALK_SCOPE_OPENID = "openid"
