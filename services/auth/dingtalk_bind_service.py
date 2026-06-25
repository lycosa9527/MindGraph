"""Universal DingTalk QR account binding.

Any channel that receives a bind QR (MindBot picture today; web upload, SMS, etc. later)
must call :func:`claim_dingtalk_qr_bind` with ``(token, bind_code, organization_id, dingtalk_staff_id)``.

Rules (per organization):
- One MindGraph user ↔ at most one DingTalk ``staff_id``.
- One DingTalk ``staff_id`` ↔ at most one MindGraph user.
- Re-binding the same pair is idempotent; binding a new staff replaces the user's prior link.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError

from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_INTERNAL,
    BIND_ERROR_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN,
    BIND_ERROR_TOKEN_CONSUMED,
    BIND_ERROR_TOKEN_EXPIRED,
)
from services.auth.dingtalk_bind_redis import (
    bind_code_secret_from_payload,
    clear_bind_code_guess_failures,
    consume_bind_token,
    get_bind_token_consumed,
    get_bind_token_data,
    is_bind_code_guess_blocked,
    record_bind_code_guess_failure,
)
from services.auth.quick_register_room_code import verify_room_code_submitted
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

logger = logging.getLogger(__name__)

__all__ = [
    "claim_dingtalk_qr_bind",
    "BIND_ERROR_STAFF_TAKEN",
]


def _parse_token_user_org(data: dict[str, Any]) -> tuple[int, int] | None:
    """Return (user_id, org_id) from mint payload or None when invalid."""
    raw_user_id = data.get("user_id")
    raw_org_id = data.get("organization_id")
    if not isinstance(raw_user_id, int) and not (isinstance(raw_user_id, str) and raw_user_id.isdigit()):
        return None
    if not isinstance(raw_org_id, int) and not (isinstance(raw_org_id, str) and raw_org_id.isdigit()):
        return None
    return int(raw_user_id), int(raw_org_id)


async def claim_dingtalk_qr_bind(
    *,
    token: str,
    bind_code: str,
    organization_id: int,
    dingtalk_staff_id: str,
    linked_via: str = "qr_bind",
) -> tuple[bool, str]:
    """
    Consume a minted bind token and link DingTalk staff to the MindGraph user.

    Returns ``(success, error_code)``. ``error_code`` is empty on success.

    Validates org, payload, and staff availability before persisting. The Redis token
    is consumed only after a successful DB commit so recoverable failures do not
    burn the QR.
    """
    stripped_token = token.strip()
    stripped_code = (bind_code or "").strip()

    if not stripped_code or len(stripped_code) != 6 or not stripped_code.isdigit():
        staff = (dingtalk_staff_id or "").strip()
        if staff:
            await record_bind_code_guess_failure(staff, stripped_token)
        return False, BIND_ERROR_TOKEN_EXPIRED

    if await get_bind_token_consumed(stripped_token):
        return False, BIND_ERROR_TOKEN_CONSUMED

    data = await get_bind_token_data(stripped_token)
    if data is None:
        return False, BIND_ERROR_TOKEN_EXPIRED

    staff = (dingtalk_staff_id or "").strip()
    if staff and await is_bind_code_guess_blocked(staff, stripped_token):
        return False, BIND_ERROR_TOKEN_EXPIRED

    bind_secret = bind_code_secret_from_payload(data)
    if not bind_secret:
        return False, BIND_ERROR_INTERNAL

    if not verify_room_code_submitted(bind_secret, stripped_token, stripped_code):
        if staff:
            await record_bind_code_guess_failure(staff, stripped_token)
        return False, BIND_ERROR_TOKEN_EXPIRED

    parsed = _parse_token_user_org(data)
    if parsed is None:
        return False, BIND_ERROR_INTERNAL

    token_user_id, token_org_id = parsed

    if token_org_id != int(organization_id):
        return False, BIND_ERROR_ORG_MISMATCH

    staff_id = staff[:128]
    if not staff_id:
        return False, BIND_ERROR_INTERNAL

    ctx = RlsContext.for_celery_user(token_user_id, organization_id=token_org_id)
    try:
        async with rls_async_session(ctx) as db:
            repo = DingtalkStaffLinkRepository(db)
            staff_row = await repo.get_by_staff(token_org_id, staff_id)
            if staff_row is not None and int(staff_row.user_id) != token_user_id:
                return False, BIND_ERROR_STAFF_TAKEN
            result = await repo.claim_staff_link(
                organization_id=token_org_id,
                dingtalk_staff_id=staff_id,
                user_id=token_user_id,
                linked_via=linked_via,
            )
            if not result.ok:
                return False, result.error_code
            await db.commit()
    except IntegrityError as exc:
        logger.warning("[DingtalkBind] claim integrity error: %s", exc)
        return False, BIND_ERROR_STAFF_TAKEN
    except DATABASE_ERRORS as exc:
        logger.warning("[DingtalkBind] claim database error: %s", exc)
        return False, BIND_ERROR_INTERNAL
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[DingtalkBind] claim failed: %s", exc)
        return False, BIND_ERROR_INTERNAL

    consumed = await consume_bind_token(stripped_token)
    if consumed is None and not await get_bind_token_consumed(stripped_token):
        logger.warning(
            "[DingtalkBind] commit ok but consume failed user_id=%s org_id=%s",
            token_user_id,
            token_org_id,
        )

    if staff:
        await clear_bind_code_guess_failures(staff, stripped_token)

    return True, ""
