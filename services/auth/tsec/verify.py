"""Fail-closed Tencent T-Sec ticket verification."""

from __future__ import annotations

import logging
from typing import Optional

from services.auth.tsec.client import TsecCaptchaClientError, describe_captcha_result

logger = logging.getLogger(__name__)

CAPTCHA_CODE_OK = 1
EVIL_LEVEL_MALICIOUS = 100
_DISASTER_PREFIXES = ("trerror_", "terror_")


async def verify_tsec_ticket(
    ticket: Optional[str],
    randstr: Optional[str],
    user_ip: str,
) -> tuple[bool, Optional[str]]:
    """Verify a T-Sec ticket with DescribeCaptchaResult.

    Returns (True, None) on CaptchaCode==1. Otherwise (False, reason).
    Disaster tickets (trerror_/terror_) are rejected without calling Tencent.
    """
    clean_ticket = (ticket or "").strip()
    clean_randstr = (randstr or "").strip()
    if not clean_ticket or not clean_randstr:
        return False, "missing_ticket"
    if clean_ticket.startswith(_DISASTER_PREFIXES):
        logger.warning("T-Sec disaster ticket rejected: %s...", clean_ticket[:24])
        return False, "disaster_ticket"

    clean_ip = (user_ip or "").strip() or "0.0.0.0"
    try:
        resp = await describe_captcha_result(clean_ticket, clean_randstr, clean_ip)
    except TsecCaptchaClientError as exc:
        logger.warning("T-Sec ticket check failed: %s", exc)
        return False, "provider_error"

    raw_code = resp.get("CaptchaCode")
    if raw_code is None:
        return False, "invalid_captcha_code"
    try:
        captcha_code = int(raw_code)
    except (TypeError, ValueError):
        return False, "invalid_captcha_code"

    if captcha_code != CAPTCHA_CODE_OK:
        logger.warning(
            "T-Sec CaptchaCode=%s msg=%s request_id=%s",
            captcha_code,
            resp.get("CaptchaMsg"),
            resp.get("RequestId"),
        )
        return False, f"captcha_code_{captcha_code}"

    evil_level = resp.get("EvilLevel")
    if evil_level == EVIL_LEVEL_MALICIOUS:
        logger.warning("T-Sec EvilLevel=100 request_id=%s", resp.get("RequestId"))
        return False, "evil_level"

    return True, None
