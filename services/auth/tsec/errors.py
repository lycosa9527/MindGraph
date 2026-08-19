"""Official Tencent T-Sec error catalogs (fail-closed; names are for logs).

Cloud API Error.Code:
https://cloud.tencent.com/document/product/1110/36927
https://cloud.tencent.com/document/api/1110/36926 (section 6)

DescribeCaptchaResult CaptchaCode (Web/App):
https://cloud.tencent.com/document/api/1110/36926
https://cloud.tencent.com/document/product/1110/84005
"""

from __future__ import annotations

CAPTCHA_CODE_OK = 1
EVIL_LEVEL_MALICIOUS = 100

# Web/App DescribeCaptchaResult. Mini-only codes (10/25/31) are not used here.
CAPTCHA_CODE_REASONS: dict[int, str] = {
    7: "randstr_mismatch",
    8: "ticket_expired",
    9: "ticket_reused",
    15: "decrypt_fail",
    16: "appid_ticket_mismatch",
    21: "ticket_diff",
    26: "system_busy",
    100: "appid_secretkey_mismatch",
}

# DescribeCaptchaResult Response.Error.Code (36926 + common 36927).
CLOUD_API_ERROR_REASONS: dict[str, str] = {
    "InternalError": "cloud_api_internal",
    "MissingParameter": "cloud_api_missing_parameter",
    "UnauthorizedOperation.ErrAuth": "cloud_api_auth",
    "UnauthorizedOperation.Unauthorized": "cloud_api_unauthorized",
}

_TRANSPORT_TOKENS = frozenset(
    {
        "timeout",
        "http_error",
        "http_status",
        "invalid_json",
        "invalid_response",
    }
)


def reason_for_captcha_code(captcha_code: int) -> str:
    """Stable reason for a non-1 CaptchaCode."""
    return CAPTCHA_CODE_REASONS.get(captcha_code, f"captcha_code_{captcha_code}")


def reason_for_client_error(token: str) -> str:
    """Map transport or Cloud API Error.Code to a fail-closed reason."""
    if token in _TRANSPORT_TOKENS:
        return "provider_error"
    return CLOUD_API_ERROR_REASONS.get(token, f"cloud_api_{token}")
