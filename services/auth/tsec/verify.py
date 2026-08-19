"""Fail-closed Tencent T-Sec ticket verification."""

from __future__ import annotations

from typing import Optional

from services.auth.tsec.client import TsecCaptchaClientError, describe_captcha_result
from services.auth.tsec.errors import (
    CAPTCHA_CODE_OK,
    EVIL_LEVEL_MALICIOUS,
    reason_for_captcha_code,
    reason_for_client_error,
)
from services.auth.tsec.result import (
    TsecVerifyTrace,
    log_tsec_audit,
    parse_describe_response,
)

_DISASTER_PREFIXES = ("trerror_", "terror_")


async def verify_tsec_ticket(
    ticket: Optional[str],
    randstr: Optional[str],
    user_ip: str,
    trace: Optional[TsecVerifyTrace] = None,
) -> tuple[bool, Optional[str]]:
    """Verify a T-Sec ticket with DescribeCaptchaResult.

    Returns (True, None) on CaptchaCode==1. Otherwise (False, reason).
    Disaster tickets (trerror_/terror_) are rejected without calling Tencent.
    """
    clean_ticket = (ticket or "").strip()
    clean_randstr = (randstr or "").strip()
    clean_ip = (user_ip or "").strip() or "0.0.0.0"
    if not clean_ticket or not clean_randstr:
        log_tsec_audit("reject", "missing_ticket", clean_ip, clean_ticket, trace=trace)
        return False, "missing_ticket"
    if clean_ticket.startswith(_DISASTER_PREFIXES):
        log_tsec_audit("reject", "disaster_ticket", clean_ip, clean_ticket, trace=trace)
        return False, "disaster_ticket"

    try:
        resp = await describe_captcha_result(clean_ticket, clean_randstr, clean_ip)
    except TsecCaptchaClientError as exc:
        reason = reason_for_client_error(str(exc))
        log_tsec_audit(
            "reject",
            reason,
            clean_ip,
            clean_ticket,
            trace=trace,
            client_error=str(exc),
        )
        return False, reason

    parsed = parse_describe_response(resp)
    if parsed.captcha_code is None:
        reason = "invalid_captcha_code"
        log_tsec_audit("reject", reason, clean_ip, clean_ticket, parsed=parsed, trace=trace)
        return False, reason

    if parsed.captcha_code != CAPTCHA_CODE_OK:
        reason = reason_for_captcha_code(parsed.captcha_code)
        log_tsec_audit("reject", reason, clean_ip, clean_ticket, parsed=parsed, trace=trace)
        return False, reason

    if parsed.evil_level == EVIL_LEVEL_MALICIOUS:
        log_tsec_audit("reject", "evil_level", clean_ip, clean_ticket, parsed=parsed, trace=trace)
        return False, "evil_level"

    log_tsec_audit("pass", "ok", clean_ip, clean_ticket, parsed=parsed, trace=trace)
    return True, None
