"""
Quick registration channel: time-limited tokens for org-bound registration.

Uses a rotating 6-digit room code (HMAC, 30s) — no SMS on this path.

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Messages, Language
from models.requests.requests_auth import (
    QuickRegisterCloseRequest,
    QuickRegisterOpenRequest,
    RegisterQuickRequest,
)
from services.auth.quick_register_redis import (
    DEFAULT_TTL_SECONDS,
    ROOM_CODE_SECRET_FIELD,
    clear_minter_index_if_token_matches,
    clear_room_code_guess_failures,
    delete_token,
    delete_token_with_retries,
    effective_workshop_max_uses,
    get_token_data,
    get_workshop_usage_count,
    is_room_code_guess_blocked,
    parse_channel_type,
    parse_organization_id_from_stored_value,
    record_room_code_guess_failure,
    refresh_workshop_channel_ttl,
    revoke_previous_minted_token_for_user,
    set_minter_token,
    store_token,
    workshop_release_reservation,
    workshop_reserve_or_fail,
    WORKSHOP_DEFAULT_MAX_USES,
)
from services.auth.quick_register_room_code import (
    current_room_code_from_room_secret,
    ROOM_CODE_PERIOD_SECONDS,
    verify_room_code_submitted,
)
from services.auth.phone_uniqueness import any_user_id_with_phone
from services.redis.redis_distributed_lock import phone_registration_lock
from services.redis.rate_limiting.redis_rate_limiter import get_rate_limiter
from utils.auth import AUTH_MODE, get_client_ip, hash_password, is_admin, is_manager
from services.monitoring.registration_metrics import registration_metrics

from .dependencies import get_language_dependency, require_admin_or_manager
from .registration import finalize_sms_registration_session
from .helpers import commit_user_with_retry

logger = logging.getLogger(__name__)

router = APIRouter()
_QUICK_REG_MINT_MAX = 20
_QUICK_REG_MINT_WINDOW = 60
_QUICK_REG_CLOSE_MAX = 40
_QUICK_REG_CLOSE_WINDOW = 60
# Per-IP on POST /register-quick (each request counts, including failed room codes).
# Defaults support ~200-500 people on one shared NAT within a 2 min burst with headroom.
_DEFAULT_REGISTER_QUICK_IP_MAX = 600
_DEFAULT_REGISTER_QUICK_IP_WINDOW = 120
_DEFAULT_REGISTER_QUICK_PHONE_MAX = 15
_DEFAULT_REGISTER_QUICK_PHONE_WINDOW = 600


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw, 10)
    except (TypeError, ValueError):
        return default


_REGISTER_QUICK_IP_MAX = _int_env("QUICK_REGISTER_IP_MAX", _DEFAULT_REGISTER_QUICK_IP_MAX)
_REGISTER_QUICK_IP_WINDOW = _int_env("QUICK_REGISTER_IP_WINDOW", _DEFAULT_REGISTER_QUICK_IP_WINDOW)
_REGISTER_QUICK_PHONE_MAX = _int_env("QUICK_REGISTER_PHONE_MAX", _DEFAULT_REGISTER_QUICK_PHONE_MAX)
_REGISTER_QUICK_PHONE_WINDOW = _int_env("QUICK_REGISTER_PHONE_WINDOW", _DEFAULT_REGISTER_QUICK_PHONE_WINDOW)
_ROOM_CODE_GET_IP_MAX = _int_env("QUICK_REG_ROOM_GET_IP_MAX", 60)
_ROOM_CODE_GET_IP_WINDOW = _int_env("QUICK_REG_ROOM_GET_IP_WINDOW", 60)
_ROOM_CODE_GET_PER_TOKEN_MAX = _int_env("QUICK_REG_ROOM_GET_TOKEN_MAX", 240)
_ROOM_CODE_GET_PER_TOKEN_WINDOW = _int_env("QUICK_REG_ROOM_GET_TOKEN_WINDOW", 60)


def _token_log_id(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]


def _minter_id_from_token_payload(data: object) -> int:
    if not isinstance(data, dict):
        return 0
    raw = data.get("created_by_user_id")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _room_code_secret_from_payload(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    raw = data.get(ROOM_CODE_SECRET_FIELD)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


@router.get("/quick-register/room-code")
async def quick_register_room_code(
    http_request: Request,
    token: str = Query(..., min_length=20, max_length=512),
    lang: Language = Depends(get_language_dependency),
):
    """Public: current 6-digit room code and server time (for modal sync)."""
    rate = get_rate_limiter()
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    allowed, _, _ = await rate.check_and_record(
        "quick_reg_room_get_ip", client_ip, _ROOM_CODE_GET_IP_MAX, _ROOM_CODE_GET_IP_WINDOW
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_rate_limited", lang),
        )
    tsha = _token_log_id(token)
    allowed_t, _, _ = await rate.check_and_record(
        "quick_reg_room_get_tok", tsha, _ROOM_CODE_GET_PER_TOKEN_MAX, _ROOM_CODE_GET_PER_TOKEN_WINDOW
    )
    if not allowed_t:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_rate_limited", lang),
        )

    token_payload = await get_token_data(token)
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("quick_reg_channel_invalid", lang),
        )

    signups_count = (
        await get_workshop_usage_count(token)
        if parse_channel_type(token_payload) == "workshop"
        else 0
    )
    room_sec = _room_code_secret_from_payload(token_payload)
    if not room_sec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("quick_reg_channel_invalid", lang),
        )
    code, step, next_start, now = current_room_code_from_room_secret(room_sec, token)
    return {
        "code": code,
        "period_seconds": ROOM_CODE_PERIOD_SECONDS,
        "server_time_unix": now,
        "time_step": step,
        "valid_until_unix": float(next_start),
        "signups_count": int(signups_count),
    }


@router.post("/quick-register/open")
async def quick_register_open(
    request_body: QuickRegisterOpenRequest,
    http_request: Request,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Mint a short-lived token bound to an organization (managers: own org; admins: body org_id)."""
    rate = get_rate_limiter()
    allowed, _count, _ = await rate.check_and_record(
        "quick_reg_mint", str(current_user.id), _QUICK_REG_MINT_MAX, _QUICK_REG_MINT_WINDOW
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_rate_limited", lang),
        )

    if AUTH_MODE in ("demo", "bayi"):
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    if is_manager(current_user) and not is_admin(current_user):
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("quick_reg_manager_org_required", lang),
            )
        org_id: int = int(current_user.organization_id)
    else:
        if request_body.organization_id is None:
            error_msg = Messages.error("missing_required_fields", lang, "organization_id")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        org_id = int(request_body.organization_id)

    res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, org_id),
        )
    if hasattr(org, "is_active") and not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("organization_not_active", lang),
        )

    ch = request_body.channel_type
    uid = int(current_user.id)
    await revoke_previous_minted_token_for_user(uid)
    token = secrets.token_urlsafe(32)
    if ch == "workshop":
        max_stored = request_body.max_uses if request_body.max_uses is not None else WORKSHOP_DEFAULT_MAX_USES
        ok = await store_token(
            token, org_id, uid, channel_type="workshop", max_uses=int(max_stored)
        )
    else:
        ok = await store_token(token, org_id, uid, channel_type="single_use", max_uses=None)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("quick_reg_redis_unavailable", lang),
        )
    if not await set_minter_token(uid, token, DEFAULT_TTL_SECONDS):
        logger.warning(
            "[QuickReg] minter index not set user_id=%s token_sha=%s",
            uid,
            _token_log_id(token),
        )

    client_ip = get_client_ip(http_request) if http_request else "unknown"
    logger.info(
        "[QuickReg] open user_id=%s org_id=%s token_sha=%s ip=%s channel=%s",
        current_user.id,
        org_id,
        _token_log_id(token),
        client_ip,
        ch,
    )
    return {"token": token}


@router.post("/quick-register/close")
async def quick_register_close(
    request_body: QuickRegisterCloseRequest,
    http_request: Request,
    current_user: User = Depends(require_admin_or_manager),
    lang: Language = Depends(get_language_dependency),
):
    """Revoke a quick-registration token (creator or full admin)."""
    rate = get_rate_limiter()
    allowed, _c, _ = await rate.check_and_record(
        "quick_reg_close", str(current_user.id), _QUICK_REG_CLOSE_MAX, _QUICK_REG_CLOSE_WINDOW
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_rate_limited", lang),
        )

    data = await get_token_data(request_body.token)
    if not data:
        return {"ok": True, "revoked": False}

    creator_id = int(data.get("created_by_user_id", 0))
    if not is_admin(current_user) and creator_id != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("quick_reg_close_forbidden", lang),
        )

    await delete_token(request_body.token)
    await clear_minter_index_if_token_matches(creator_id, request_body.token)
    logger.info(
        "[QuickReg] close user_id=%s token_sha=%s ip=%s",
        current_user.id,
        _token_log_id(request_body.token),
        get_client_ip(http_request) if http_request else "unknown",
    )
    return {"ok": True, "revoked": True}


@router.post("/register-quick")
async def register_quick(
    request: RegisterQuickRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Register with phone, room code, and quick_reg_token (no SMS on this path)."""
    if AUTH_MODE in ("demo", "bayi"):
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    registration_metrics.record_attempt()
    start_time = time.time()
    retry_count = 0
    err_detail = Messages.error("quick_reg_channel_invalid", lang)
    new_user: User | None = None

    rate = get_rate_limiter()
    client_ip = get_client_ip(http_request) if http_request else "unknown"
    allowed, _a, _ = await rate.check_and_record(
        "register_quick_ip", client_ip, _REGISTER_QUICK_IP_MAX, _REGISTER_QUICK_IP_WINDOW
    )
    if not allowed:
        registration_metrics.record_register_quick_throttled("ip")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_rate_limited", lang),
        )

    data = await get_token_data(request.quick_reg_token)
    if not data:
        registration_metrics.record_failure("invitation_code_invalid", time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_detail,
        )

    org_id = parse_organization_id_from_stored_value(data)
    if org_id is None:
        registration_metrics.record_failure("invitation_code_invalid", time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_detail,
        )
    res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalar_one_or_none()
    if not org or (hasattr(org, "is_active") and not org.is_active):
        registration_metrics.record_failure("invitation_code_invalid", time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_detail,
        )

    if await is_room_code_guess_blocked(client_ip, request.quick_reg_token):
        registration_metrics.record_register_quick_throttled("room_guess")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_room_too_many_guesses", lang),
        )

    allowed_phone, _, _ = await rate.check_and_record(
        "register_quick_phone", request.phone, _REGISTER_QUICK_PHONE_MAX, _REGISTER_QUICK_PHONE_WINDOW
    )
    if not allowed_phone:
        registration_metrics.record_register_quick_throttled("phone")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=Messages.error("quick_reg_rate_limited", lang),
        )

    room_stripped = request.room_code.strip()
    if len(room_stripped) != 6 or not room_stripped.isdigit():
        registration_metrics.record_failure("room_code_invalid", time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("quick_reg_room_code_invalid", lang),
        )
    room_hsec = _room_code_secret_from_payload(data)
    if not room_hsec:
        registration_metrics.record_failure("invitation_code_invalid", time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_detail,
        )
    if not verify_room_code_submitted(room_hsec, request.quick_reg_token, room_stripped):
        await record_room_code_guess_failure(client_ip, request.quick_reg_token)
        registration_metrics.record_failure("room_code_invalid", time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("quick_reg_room_code_invalid", lang),
        )

    ch = parse_channel_type(data)
    wmax = effective_workshop_max_uses(data) if ch == "workshop" else 0
    minter_id_for_token = _minter_id_from_token_payload(data)
    placeholder_password = hash_password(secrets.token_urlsafe(32))
    reserved_workshop = False
    n_after = 0

    try:
        async with phone_registration_lock(request.phone):
            if await any_user_id_with_phone(db, request.phone) is not None:
                registration_metrics.record_failure("phone_exists", time.time() - start_time)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=Messages.error("phone_already_registered", lang),
                )
            if not await get_token_data(request.quick_reg_token):
                registration_metrics.record_failure("invitation_code_invalid", time.time() - start_time)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=err_detail,
                )
            if ch == "workshop":
                st, n_after = await workshop_reserve_or_fail(request.quick_reg_token, wmax)
                if st == "no_token":
                    registration_metrics.record_failure("invitation_code_invalid", time.time() - start_time)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=err_detail,
                    )
                if st == "full":
                    registration_metrics.record_failure("workshop_full", time.time() - start_time)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=Messages.error("quick_reg_workshop_full", lang),
                    )
                if st == "redis_error":
                    registration_metrics.record_failure("other", time.time() - start_time)
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=Messages.error("quick_reg_redis_unavailable", lang),
                    )
                reserved_workshop = True

            new_user = User(
                phone=request.phone,
                password_hash=placeholder_password,
                name=None,
                organization_id=org.id,
                created_at=datetime.now(UTC),
                role="user",
                login_password_set=False,
            )
            db.add(new_user)
            try:
                retry_count = await commit_user_with_retry(
                    db, new_user, max_retries=5, lang=lang
                )
            except HTTPException:
                if reserved_workshop:
                    await workshop_release_reservation(request.quick_reg_token)
                raise
            if ch == "single_use":
                deleted = await delete_token_with_retries(request.quick_reg_token)
                if minter_id_for_token and request.quick_reg_token:
                    await clear_minter_index_if_token_matches(
                        minter_id_for_token, request.quick_reg_token
                    )
                if not deleted:
                    registration_metrics.record_quick_reg_token_delete_failed()
                    logger.error(
                        (
                            "[QuickReg] CRITICAL: token delete failed after commit user_id=%s org_id=%s"
                            " token_sha=%s"
                        ),
                        new_user.id,
                        org_id,
                        _token_log_id(request.quick_reg_token),
                    )
            else:
                at_cap = n_after >= wmax
                if at_cap:
                    deleted = await delete_token_with_retries(request.quick_reg_token)
                    if minter_id_for_token and request.quick_reg_token:
                        await clear_minter_index_if_token_matches(
                            minter_id_for_token, request.quick_reg_token
                        )
                    if not deleted:
                        registration_metrics.record_quick_reg_token_delete_failed()
                        logger.error(
                            (
                                "[QuickReg] CRITICAL: token delete failed after last workshop slot "
                                "user_id=%s org_id=%s token_sha=%s"
                            ),
                            new_user.id,
                            org_id,
                            _token_log_id(request.quick_reg_token),
                        )
                else:
                    await refresh_workshop_channel_ttl(
                        request.quick_reg_token, minter_id_for_token, DEFAULT_TTL_SECONDS
                    )
    except HTTPException:
        raise
    except RuntimeError as exc:
        registration_metrics.record_failure("lock_timeout", time.time() - start_time)
        logger.warning(
            "[QuickReg] phone lock not acquired: %s",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("quick_reg_redis_unavailable", lang),
        ) from exc
    except Exception:
        registration_metrics.record_failure("other", time.time() - start_time)
        raise

    if new_user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("internal_error", lang),
        )
    await clear_room_code_guess_failures(client_ip, request.quick_reg_token)
    _phone_tail = request.phone[-3:] if len(request.phone) >= 3 else ""
    logger.info(
        (
            "[TokenAudit] quick register user_id=%s org_id=%s phone_tail=***%s method=register_quick ip=%s"
        ),
        new_user.id,
        org_id,
        _phone_tail,
        client_ip,
    )

    return await finalize_sms_registration_session(
        new_user=new_user,
        org=org,
        http_request=http_request,
        response=response,
        db=db,
        start_time=start_time,
        retry_count=retry_count,
        register_action="register_quick",
    )
