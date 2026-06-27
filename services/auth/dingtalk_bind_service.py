"""Universal DingTalk account pairing (bind and unbind)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.exc import IntegrityError

from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from services.auth.dingtalk_bind_audit_log import log_claim_failed, log_claim_ok
from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_INTERNAL,
    BIND_ERROR_ORG_MISMATCH,
    BIND_ERROR_STAFF_TAKEN,
    BIND_ERROR_TOKEN_CONSUMED,
    BIND_ERROR_TOKEN_EXPIRED,
    BIND_ERROR_UNBIND_NOT_LINKED,
    BIND_ERROR_UNBIND_STAFF_MISMATCH,
    PAIR_PURPOSE_BIND,
    PAIR_PURPOSE_UNBIND,
)
from services.auth.dingtalk_bind_redis import (
    bind_code_secret_from_payload,
    clear_bind_code_guess_failures,
    consume_bind_token,
    force_burn_bind_token,
    get_bind_token_consumed,
    get_bind_token_data,
    is_bind_code_guess_blocked,
    pair_purpose_from_payload,
    record_bind_code_guess_failure,
    release_pair_claim_lock,
    try_acquire_pair_claim_lock,
)
from services.auth.quick_register_room_code import verify_room_code_submitted
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

logger = logging.getLogger(__name__)

__all__ = [
    "claim_dingtalk_qr_bind",
    "claim_dingtalk_unbind_pair",
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


def _log_claim_failure(
    *,
    action: str,
    data: dict[str, Any] | None,
    organization_id: int,
    staff_id: str,
    error_code: str,
) -> None:
    parsed = _parse_token_user_org(data) if data is not None else None
    user_id = parsed[0] if parsed is not None else None
    org_id = parsed[1] if parsed is not None else int(organization_id)
    log_claim_failed(
        action=action,
        user_id=user_id,
        org_id=org_id,
        staff_id=staff_id,
        error_code=error_code,
    )


async def _verify_pair_code(
    *,
    token: str,
    bind_code: str,
    organization_id: int,
    dingtalk_staff_id: str,
    expected_purpose: str,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Shared rotating-code verification for bind/unbind pair sessions."""
    stripped_token = token.strip()
    stripped_code = (bind_code or "").strip()
    staff = (dingtalk_staff_id or "").strip()

    if not stripped_code or len(stripped_code) != 6 or not stripped_code.isdigit():
        if staff:
            await record_bind_code_guess_failure(staff, stripped_token)
        return False, BIND_ERROR_TOKEN_EXPIRED, None

    if await get_bind_token_consumed(stripped_token):
        return False, BIND_ERROR_TOKEN_CONSUMED, None

    data = await get_bind_token_data(stripped_token)
    if data is None:
        return False, BIND_ERROR_TOKEN_EXPIRED, None

    if staff and await is_bind_code_guess_blocked(staff, stripped_token):
        return False, BIND_ERROR_TOKEN_EXPIRED, None

    if pair_purpose_from_payload(data) != expected_purpose:
        if staff:
            await record_bind_code_guess_failure(staff, stripped_token)
        return False, BIND_ERROR_TOKEN_EXPIRED, None

    bind_secret = bind_code_secret_from_payload(data)
    if not bind_secret:
        return False, BIND_ERROR_INTERNAL, None

    if not verify_room_code_submitted(bind_secret, stripped_token, stripped_code):
        if staff:
            await record_bind_code_guess_failure(staff, stripped_token)
        return False, BIND_ERROR_TOKEN_EXPIRED, None

    parsed = _parse_token_user_org(data)
    if parsed is None:
        return False, BIND_ERROR_INTERNAL, None

    _token_user_id, token_org_id = parsed
    if token_org_id != int(organization_id):
        return False, BIND_ERROR_ORG_MISMATCH, None

    if not staff[:128]:
        return False, BIND_ERROR_INTERNAL, None

    return True, "", data


async def _finalize_successful_claim(
    *,
    stripped_token: str,
    staff_id: str,
    token_user_id: int,
    token_org_id: int,
    action_label: str,
) -> tuple[bool, str, bool]:
    """Consume Redis token after DB commit; return (ok, err, consumed)."""
    for attempt in range(3):
        consumed = await consume_bind_token(stripped_token)
        if consumed is not None:
            if staff_id:
                await clear_bind_code_guess_failures(staff_id, stripped_token)
            return True, "", True
        if await get_bind_token_consumed(stripped_token):
            if staff_id:
                await clear_bind_code_guess_failures(staff_id, stripped_token)
            return True, "", True
        if attempt < 2:
            await asyncio.sleep(0.05)

    burned = await force_burn_bind_token(stripped_token)
    if burned:
        if staff_id:
            await clear_bind_code_guess_failures(staff_id, stripped_token)
        logger.error(
            "[DingtalkBind] %s commit ok; token force-burned user_id=%s org_id=%s",
            action_label,
            token_user_id,
            token_org_id,
        )
        return True, "", True

    logger.error(
        "[DingtalkBind] %s commit ok but consume failed user_id=%s org_id=%s",
        action_label,
        token_user_id,
        token_org_id,
    )
    return False, BIND_ERROR_INTERNAL, False


async def claim_dingtalk_qr_bind(
    *,
    token: str,
    bind_code: str,
    organization_id: int,
    dingtalk_staff_id: str,
    linked_via: str = "code_bind",
) -> tuple[bool, str]:
    """Consume a bind pair session and link DingTalk staff to the MindGraph user."""
    staff_id = (dingtalk_staff_id or "").strip()[:128]
    ok, err_code, data = await _verify_pair_code(
        token=token,
        bind_code=bind_code,
        organization_id=organization_id,
        dingtalk_staff_id=staff_id,
        expected_purpose=PAIR_PURPOSE_BIND,
    )
    if not ok or data is None:
        _log_claim_failure(
            action="bind",
            data=data,
            organization_id=organization_id,
            staff_id=staff_id,
            error_code=err_code,
        )
        return ok, err_code

    stripped_token = token.strip()
    if not await try_acquire_pair_claim_lock(stripped_token):
        if await get_bind_token_consumed(stripped_token):
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_TOKEN_CONSUMED,
            )
            return False, BIND_ERROR_TOKEN_CONSUMED
        _log_claim_failure(
            action="bind",
            data=data,
            organization_id=organization_id,
            staff_id=staff_id,
            error_code=BIND_ERROR_TOKEN_EXPIRED,
        )
        return False, BIND_ERROR_TOKEN_EXPIRED

    release_lock = True
    try:
        if await get_bind_token_consumed(stripped_token):
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_TOKEN_CONSUMED,
            )
            return False, BIND_ERROR_TOKEN_CONSUMED

        parsed = _parse_token_user_org(data)
        if parsed is None:
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_INTERNAL,
            )
            return False, BIND_ERROR_INTERNAL
        token_user_id, token_org_id = parsed

        ctx = RlsContext.for_celery_user(token_user_id, organization_id=token_org_id)
        try:
            async with rls_async_session(ctx) as db:
                repo = DingtalkStaffLinkRepository(db)
                staff_row = await repo.get_by_staff(token_org_id, staff_id)
                if staff_row is not None and int(staff_row.user_id) != token_user_id:
                    _log_claim_failure(
                        action="bind",
                        data=data,
                        organization_id=organization_id,
                        staff_id=staff_id,
                        error_code=BIND_ERROR_STAFF_TAKEN,
                    )
                    return False, BIND_ERROR_STAFF_TAKEN
                result = await repo.claim_staff_link(
                    organization_id=token_org_id,
                    dingtalk_staff_id=staff_id,
                    user_id=token_user_id,
                    linked_via=linked_via,
                )
                if not result.ok:
                    _log_claim_failure(
                        action="bind",
                        data=data,
                        organization_id=organization_id,
                        staff_id=staff_id,
                        error_code=result.error_code,
                    )
                    return False, result.error_code
                await db.commit()
        except IntegrityError as exc:
            logger.warning("[DingtalkBind] claim integrity error: %s", exc)
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_STAFF_TAKEN,
            )
            return False, BIND_ERROR_STAFF_TAKEN
        except DATABASE_ERRORS as exc:
            logger.warning("[DingtalkBind] claim database error: %s", exc)
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_INTERNAL,
            )
            return False, BIND_ERROR_INTERNAL
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[DingtalkBind] claim failed: %s", exc)
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_INTERNAL,
            )
            return False, BIND_ERROR_INTERNAL

        ok, err, consumed = await _finalize_successful_claim(
            stripped_token=stripped_token,
            staff_id=staff_id,
            token_user_id=token_user_id,
            token_org_id=token_org_id,
            action_label="bind",
        )
        if not consumed:
            release_lock = False
        if ok:
            log_claim_ok(
                action="bind",
                user_id=token_user_id,
                org_id=token_org_id,
                staff_id=staff_id,
                linked_via=linked_via,
            )
        elif err:
            _log_claim_failure(
                action="bind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=err,
            )
        return ok, err
    finally:
        if release_lock:
            await release_pair_claim_lock(stripped_token)


async def claim_dingtalk_unbind_pair(
    *,
    token: str,
    bind_code: str,
    organization_id: int,
    dingtalk_staff_id: str,
) -> tuple[bool, str]:
    """Consume an unbind pair session after the linked DingTalk staff confirms the code."""
    staff_id = (dingtalk_staff_id or "").strip()[:128]
    ok, err_code, data = await _verify_pair_code(
        token=token,
        bind_code=bind_code,
        organization_id=organization_id,
        dingtalk_staff_id=staff_id,
        expected_purpose=PAIR_PURPOSE_UNBIND,
    )
    if not ok or data is None:
        _log_claim_failure(
            action="unbind",
            data=data,
            organization_id=organization_id,
            staff_id=staff_id,
            error_code=err_code,
        )
        return ok, err_code

    stripped_token = token.strip()
    if not await try_acquire_pair_claim_lock(stripped_token):
        if await get_bind_token_consumed(stripped_token):
            _log_claim_failure(
                action="unbind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_TOKEN_CONSUMED,
            )
            return False, BIND_ERROR_TOKEN_CONSUMED
        _log_claim_failure(
            action="unbind",
            data=data,
            organization_id=organization_id,
            staff_id=staff_id,
            error_code=BIND_ERROR_TOKEN_EXPIRED,
        )
        return False, BIND_ERROR_TOKEN_EXPIRED

    release_lock = True
    try:
        if await get_bind_token_consumed(stripped_token):
            _log_claim_failure(
                action="unbind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_TOKEN_CONSUMED,
            )
            return False, BIND_ERROR_TOKEN_CONSUMED

        parsed = _parse_token_user_org(data)
        if parsed is None:
            _log_claim_failure(
                action="unbind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_INTERNAL,
            )
            return False, BIND_ERROR_INTERNAL
        token_user_id, token_org_id = parsed

        ctx = RlsContext.for_celery_user(token_user_id, organization_id=token_org_id)
        try:
            async with rls_async_session(ctx) as db:
                repo = DingtalkStaffLinkRepository(db)
                link = await repo.get_for_user(token_org_id, token_user_id)
                if link is None:
                    _log_claim_failure(
                        action="unbind",
                        data=data,
                        organization_id=organization_id,
                        staff_id=staff_id,
                        error_code=BIND_ERROR_UNBIND_NOT_LINKED,
                    )
                    return False, BIND_ERROR_UNBIND_NOT_LINKED
                if link.dingtalk_staff_id != staff_id:
                    _log_claim_failure(
                        action="unbind",
                        data=data,
                        organization_id=organization_id,
                        staff_id=staff_id,
                        error_code=BIND_ERROR_UNBIND_STAFF_MISMATCH,
                    )
                    return False, BIND_ERROR_UNBIND_STAFF_MISMATCH
                removed = await repo.delete_for_user(token_org_id, token_user_id)
                if not removed:
                    _log_claim_failure(
                        action="unbind",
                        data=data,
                        organization_id=organization_id,
                        staff_id=staff_id,
                        error_code=BIND_ERROR_UNBIND_NOT_LINKED,
                    )
                    return False, BIND_ERROR_UNBIND_NOT_LINKED
                await db.commit()
        except DATABASE_ERRORS as exc:
            logger.warning("[DingtalkBind] unbind database error: %s", exc)
            _log_claim_failure(
                action="unbind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_INTERNAL,
            )
            return False, BIND_ERROR_INTERNAL
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[DingtalkBind] unbind failed: %s", exc)
            _log_claim_failure(
                action="unbind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=BIND_ERROR_INTERNAL,
            )
            return False, BIND_ERROR_INTERNAL

        ok, err, consumed = await _finalize_successful_claim(
            stripped_token=stripped_token,
            staff_id=staff_id,
            token_user_id=token_user_id,
            token_org_id=token_org_id,
            action_label="unbind",
        )
        if not consumed:
            release_lock = False
        if ok:
            log_claim_ok(
                action="unbind",
                user_id=token_user_id,
                org_id=token_org_id,
                staff_id=staff_id,
                linked_via="code_unbind",
            )
        elif err:
            _log_claim_failure(
                action="unbind",
                data=data,
                organization_id=organization_id,
                staff_id=staff_id,
                error_code=err,
            )
        return ok, err
    finally:
        if release_lock:
            await release_pair_claim_lock(stripped_token)
