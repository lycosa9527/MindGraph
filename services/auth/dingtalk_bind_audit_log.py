"""Structured audit logging for DingTalk bind web API and DB claims."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_WEB_PREFIX = "[DingtalkBind:web]"
_CLAIM_PREFIX = "[DingtalkBind:claim]"


def _token_tail(token: str) -> str:
    text = (token or "").strip()
    if len(text) <= 8:
        return "****"
    return f"…{text[-8:]}"


def _staff_label(staff_id: str) -> str:
    text = (staff_id or "").strip()
    if not text:
        return "-"
    if len(text) <= 20:
        return text
    return f"{text[:20]}…"


def log_web_mint_started(*, user_id: int, org_id: int, purpose: str) -> None:
    """User opened bind/unbind pair flow on the web."""
    logger.info(
        "%s mint_started user_id=%s org_id=%s purpose=%s",
        _WEB_PREFIX,
        user_id,
        org_id,
        purpose,
    )


def log_web_mint_ok(*, user_id: int, org_id: int, purpose: str, token: str) -> None:
    """Pair session stored in Redis after web mint."""
    logger.info(
        "%s mint_ok user_id=%s org_id=%s purpose=%s token=%s",
        _WEB_PREFIX,
        user_id,
        org_id,
        purpose,
        _token_tail(token),
    )


def log_web_mint_failed(*, user_id: int, org_id: int, purpose: str, reason: str) -> None:
    """Web mint rejected or Redis store failed."""
    logger.warning(
        "%s mint_failed user_id=%s org_id=%s purpose=%s reason=%s",
        _WEB_PREFIX,
        user_id,
        org_id,
        purpose,
        reason,
    )


def log_web_cancel(*, user_id: int) -> None:
    """User closed pair modal or cancelled pending session."""
    logger.info("%s cancel user_id=%s", _WEB_PREFIX, user_id)


def log_web_room_code_refresh(
    *,
    user_id: int,
    org_id: int,
    purpose: str,
    token: str,
) -> None:
    """Room-code poll refreshed the rotating pair display (debug only)."""
    logger.debug(
        "%s room_code_refresh user_id=%s org_id=%s purpose=%s token=%s",
        _WEB_PREFIX,
        user_id,
        org_id,
        purpose,
        _token_tail(token),
    )


def log_claim_ok(
    *,
    action: str,
    user_id: int,
    org_id: int,
    staff_id: str,
    linked_via: str = "code_bind",
) -> None:
    """DB link created or removed after successful pair-code claim."""
    logger.info(
        "%s ok action=%s user_id=%s org_id=%s staff=%s linked_via=%s",
        _CLAIM_PREFIX,
        action,
        user_id,
        org_id,
        _staff_label(staff_id),
        linked_via,
    )


def log_claim_failed(
    *,
    action: str,
    user_id: int | None,
    org_id: int,
    staff_id: str,
    error_code: str,
) -> None:
    """Pair-code claim rejected before or during DB work."""
    logger.warning(
        "%s failed action=%s user_id=%s org_id=%s staff=%s error=%s",
        _CLAIM_PREFIX,
        action,
        user_id if user_id is not None else "-",
        org_id,
        _staff_label(staff_id),
        error_code,
    )
