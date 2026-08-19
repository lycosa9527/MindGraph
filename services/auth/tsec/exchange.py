"""Mint a one-time SVG-compatible captcha session after a T-Sec pass."""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import Optional

from services.auth.captcha_storage import get_captcha_storage
from services.auth.tsec.verify import verify_tsec_ticket
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 4
_TTL_SECONDS = 300


async def exchange_tsec_ticket(
    ticket: Optional[str],
    randstr: Optional[str],
    user_ip: str,
) -> tuple[Optional[dict[str, str]], Optional[str]]:
    """Verify ticket then store a 4-char Redis captcha the existing auth APIs accept.

    Returns ({captcha_id, captcha}, None) on success, or (None, error_reason).
    """
    is_valid, reason = await verify_tsec_ticket(ticket, randstr, user_ip)
    if not is_valid:
        return None, reason or "incorrect"

    captcha_id = str(uuid.uuid4())
    code = "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LENGTH))
    try:
        stored = await get_captcha_storage().store(captcha_id, code, expires_in_seconds=_TTL_SECONDS)
    except REDIS_ERRORS as exc:
        logger.error("T-Sec mint store failed: %s", exc, exc_info=True)
        return None, "store_failed"
    if not stored:
        return None, "store_failed"
    return {"captcha_id": captcha_id, "captcha": code}, None
