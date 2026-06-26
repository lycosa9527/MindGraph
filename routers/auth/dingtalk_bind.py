"""DingTalk bind API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from config.database import get_async_db
from models.domain.auth import User
from models.domain.mindbot_config import OrganizationMindbotConfig
from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from services.auth.dingtalk_bind_audit_log import (
    log_web_cancel,
    log_web_mint_failed,
    log_web_mint_ok,
    log_web_mint_started,
    log_web_room_code_refresh,
)
from services.auth.dingtalk_bind_constants import (
    BIND_TOKEN_TTL_SECONDS,
    PAIR_PURPOSE_BIND,
    PAIR_PURPOSE_UNBIND,
)
from services.auth.dingtalk_bind_redis import (
    bind_code_secret_from_payload,
    get_bind_token_data,
    get_minter_bind_token,
    get_pending_pair_purpose,
    has_pending_bind_token,
    mint_bind_token,
    pair_purpose_from_payload,
    register_bind_code_index,
    revoke_pending_bind_token,
    store_bind_token,
)
from services.auth.quick_register_room_code import (
    ROOM_CODE_PERIOD_SECONDS,
    current_room_code_from_room_secret,
)
from services.mindbot.bind.code_parse import format_bind_code_display
from services.redis.rate_limiting.redis_rate_limiter import get_rate_limiter
from utils.auth import get_current_user

router = APIRouter()
_BIND_MINT_MAX = 10
_BIND_MINT_WINDOW = 60
_BIND_STATUS_MAX = 120
_BIND_STATUS_WINDOW = 60
_BIND_ROOM_CODE_MAX = 120
_BIND_ROOM_CODE_WINDOW = 60


class DingtalkBindRoomCodeResponse(BaseModel):
    """Rotating pair code payload for modal polling."""

    code: str
    code_display: str
    pair_purpose: str = PAIR_PURPOSE_BIND
    period_seconds: int = ROOM_CODE_PERIOD_SECONDS
    valid_until_unix: float
    ttl_seconds: int = BIND_TOKEN_TTL_SECONDS
    bind_token: str


class DingtalkBindQrCodeResponse(DingtalkBindRoomCodeResponse):
    """Backward-compatible alias for older clients."""

    qr_query: str = ""


class DingtalkBindStatusResponse(BaseModel):
    """Bind status for account modal polling."""

    linked: bool
    mindbot_available: bool
    dingtalk_staff_id: Optional[str] = None
    pending_token_active: bool = False
    pending_pair_purpose: Optional[str] = None
    token_ttl_seconds: int = Field(default=BIND_TOKEN_TTL_SECONDS)
    rate_limited: bool = False


class DingtalkBindStartResponse(BaseModel):
    """Mint bind token response."""

    token: str
    ttl_seconds: int = BIND_TOKEN_TTL_SECONDS


def _bind_http_error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
    )


def _mask_staff_id(staff_id: str) -> str:
    text = (staff_id or "").strip()
    if len(text) <= 4:
        return "****"
    return f"{text[:2]}****{text[-2:]}"


async def _org_has_mindbot(db: AsyncSession, organization_id: int) -> bool:
    if not config.FEATURE_MINDBOT:
        return False
    stmt = (
        select(func.count())
        .select_from(OrganizationMindbotConfig)
        .where(
            OrganizationMindbotConfig.organization_id == int(organization_id),
            OrganizationMindbotConfig.is_enabled.is_(True),
        )
    )
    count = (await db.execute(stmt)).scalar_one()
    return int(count or 0) > 0


@router.post("/dingtalk-bind/start", response_model=DingtalkBindStartResponse)
async def dingtalk_bind_start(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> DingtalkBindStartResponse:
    """Mint a single-use bind session for the current user."""
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None or int(org_id) <= 0:
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_ORG",
            "Organization membership required for DingTalk bind",
        )

    limiter = get_rate_limiter()
    allowed, _, _ = await limiter.check_and_record(
        "dingtalk_bind_start",
        f"user:{int(current_user.id)}",
        _BIND_MINT_MAX,
        _BIND_MINT_WINDOW,
    )
    if not allowed:
        raise _bind_http_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DINGTALK_BIND_RATE_LIMIT",
            "Too many bind attempts",
        )

    if not await _org_has_mindbot(db, int(org_id)):
        log_web_mint_failed(
            user_id=int(current_user.id),
            org_id=int(org_id),
            purpose=PAIR_PURPOSE_BIND,
            reason="no_mindbot",
        )
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_MINDBOT",
            "MindBot is not enabled for your organization",
        )

    log_web_mint_started(
        user_id=int(current_user.id),
        org_id=int(org_id),
        purpose=PAIR_PURPOSE_BIND,
    )
    token = mint_bind_token()
    stored = await store_bind_token(
        token=token,
        user_id=int(current_user.id),
        organization_id=int(org_id),
    )
    if not stored:
        log_web_mint_failed(
            user_id=int(current_user.id),
            org_id=int(org_id),
            purpose=PAIR_PURPOSE_BIND,
            reason="redis_unavailable",
        )
        raise _bind_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DINGTALK_BIND_REDIS_UNAVAILABLE",
            "Bind service temporarily unavailable",
        )

    log_web_mint_ok(
        user_id=int(current_user.id),
        org_id=int(org_id),
        purpose=PAIR_PURPOSE_BIND,
        token=token,
    )
    return DingtalkBindStartResponse(token=token, ttl_seconds=BIND_TOKEN_TTL_SECONDS)


@router.post("/dingtalk-bind/unbind/start", response_model=DingtalkBindStartResponse)
async def dingtalk_unbind_start(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> DingtalkBindStartResponse:
    """Mint a single-use unbind pair session for the linked user."""
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None or int(org_id) <= 0:
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_ORG",
            "Organization membership required for DingTalk unbind",
        )

    limiter = get_rate_limiter()
    allowed, _, _ = await limiter.check_and_record(
        "dingtalk_unbind_start",
        f"user:{int(current_user.id)}",
        _BIND_MINT_MAX,
        _BIND_MINT_WINDOW,
    )
    if not allowed:
        raise _bind_http_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DINGTALK_BIND_RATE_LIMIT",
            "Too many unbind attempts",
        )

    if not await _org_has_mindbot(db, int(org_id)):
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_MINDBOT",
            "MindBot is not enabled for your organization",
        )

    repo = DingtalkStaffLinkRepository(db)
    link = await repo.get_for_user(int(org_id), int(current_user.id))
    if link is None:
        log_web_mint_failed(
            user_id=int(current_user.id),
            org_id=int(org_id),
            purpose=PAIR_PURPOSE_UNBIND,
            reason="not_linked",
        )
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NOT_LINKED",
            "No DingTalk account is linked",
        )

    log_web_mint_started(
        user_id=int(current_user.id),
        org_id=int(org_id),
        purpose=PAIR_PURPOSE_UNBIND,
    )
    token = mint_bind_token()
    stored = await store_bind_token(
        token=token,
        user_id=int(current_user.id),
        organization_id=int(org_id),
        purpose=PAIR_PURPOSE_UNBIND,
    )
    if not stored:
        log_web_mint_failed(
            user_id=int(current_user.id),
            org_id=int(org_id),
            purpose=PAIR_PURPOSE_UNBIND,
            reason="redis_unavailable",
        )
        raise _bind_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DINGTALK_BIND_REDIS_UNAVAILABLE",
            "Bind service temporarily unavailable",
        )

    log_web_mint_ok(
        user_id=int(current_user.id),
        org_id=int(org_id),
        purpose=PAIR_PURPOSE_UNBIND,
        token=token,
    )
    return DingtalkBindStartResponse(token=token, ttl_seconds=BIND_TOKEN_TTL_SECONDS)


async def _dingtalk_bind_room_code_payload(
    *,
    bind_token: str | None,
    current_user: User,
) -> DingtalkBindRoomCodeResponse:
    limiter = get_rate_limiter()
    allowed, _, _ = await limiter.check_and_record(
        "dingtalk_bind_room_code",
        f"user:{int(current_user.id)}",
        _BIND_ROOM_CODE_MAX,
        _BIND_ROOM_CODE_WINDOW,
    )
    if not allowed:
        raise _bind_http_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DINGTALK_BIND_RATE_LIMIT",
            "Too many bind code refresh requests",
        )

    channel_key = (bind_token or "").strip()
    if not channel_key:
        channel_key = await get_minter_bind_token(int(current_user.id)) or ""
    if not channel_key:
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_PENDING",
            "No active bind session",
        )

    minter_token = await get_minter_bind_token(int(current_user.id))
    if minter_token != channel_key:
        raise _bind_http_error(
            status.HTTP_403_FORBIDDEN,
            "DINGTALK_BIND_TOKEN_FORBIDDEN",
            "Bind token does not belong to the current user",
        )

    token_payload = await get_bind_token_data(channel_key)
    if token_payload is None:
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_PENDING",
            "No active bind session",
        )

    raw_user_id = token_payload.get("user_id")
    if not isinstance(raw_user_id, int) and not (isinstance(raw_user_id, str) and str(raw_user_id).isdigit()):
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_PENDING",
            "No active bind session",
        )
    if int(raw_user_id) != int(current_user.id):
        raise _bind_http_error(
            status.HTTP_403_FORBIDDEN,
            "DINGTALK_BIND_TOKEN_FORBIDDEN",
            "Bind token does not belong to the current user",
        )

    bind_secret = bind_code_secret_from_payload(token_payload)
    if not bind_secret:
        raise _bind_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DINGTALK_BIND_REDIS_UNAVAILABLE",
            "Bind service temporarily unavailable",
        )

    code, _step, next_start, _now = current_room_code_from_room_secret(bind_secret, channel_key)
    raw_org_id = token_payload.get("organization_id")
    if isinstance(raw_org_id, int):
        org_id = raw_org_id
    elif isinstance(raw_org_id, str) and raw_org_id.isdigit():
        org_id = int(raw_org_id)
    else:
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_PENDING",
            "No active bind session",
        )
    await register_bind_code_index(
        organization_id=org_id,
        token=channel_key,
        bind_secret=bind_secret,
    )
    purpose = pair_purpose_from_payload(token_payload)
    log_web_room_code_refresh(
        user_id=int(current_user.id),
        org_id=org_id,
        purpose=purpose,
        token=channel_key,
    )
    return DingtalkBindRoomCodeResponse(
        code=code,
        code_display=format_bind_code_display(code),
        pair_purpose=purpose,
        period_seconds=ROOM_CODE_PERIOD_SECONDS,
        valid_until_unix=float(next_start),
        ttl_seconds=BIND_TOKEN_TTL_SECONDS,
        bind_token=channel_key,
    )


@router.get("/dingtalk-bind/room-code", response_model=DingtalkBindRoomCodeResponse)
async def dingtalk_bind_room_code(
    bind_token: str | None = Query(default=None, min_length=20, max_length=512),
    current_user: User = Depends(get_current_user),
) -> DingtalkBindRoomCodeResponse:
    """Return the current rotating 6-digit bind code for the pending bind session."""
    return await _dingtalk_bind_room_code_payload(
        bind_token=bind_token,
        current_user=current_user,
    )


@router.get("/dingtalk-bind/qr-code", response_model=DingtalkBindQrCodeResponse)
async def dingtalk_bind_qr_code(
    bind_token: str | None = Query(default=None, min_length=20, max_length=512),
    current_user: User = Depends(get_current_user),
) -> DingtalkBindQrCodeResponse:
    """Backward-compatible alias for room-code polling."""
    payload = await _dingtalk_bind_room_code_payload(
        bind_token=bind_token,
        current_user=current_user,
    )
    return DingtalkBindQrCodeResponse(
        code=payload.code,
        code_display=payload.code_display,
        pair_purpose=payload.pair_purpose,
        period_seconds=payload.period_seconds,
        valid_until_unix=payload.valid_until_unix,
        ttl_seconds=payload.ttl_seconds,
        bind_token=payload.bind_token,
        qr_query="",
    )


@router.get("/dingtalk-bind/status", response_model=DingtalkBindStatusResponse)
async def dingtalk_bind_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> DingtalkBindStatusResponse:
    """Poll bind status for account modal."""
    org_id = getattr(current_user, "organization_id", None)
    mindbot_available = False
    linked = False
    staff_masked: Optional[str] = None

    if org_id is not None and int(org_id) > 0:
        mindbot_available = await _org_has_mindbot(db, int(org_id))
        repo = DingtalkStaffLinkRepository(db)
        link = await repo.get_for_user(int(org_id), int(current_user.id))
        if link is not None:
            linked = True
            staff_masked = _mask_staff_id(link.dingtalk_staff_id)

    limiter = get_rate_limiter()
    allowed, _, _ = await limiter.check_and_record(
        "dingtalk_bind_status",
        f"user:{int(current_user.id)}",
        _BIND_STATUS_MAX,
        _BIND_STATUS_WINDOW,
    )

    pending = False
    pending_purpose: Optional[str] = None
    if allowed:
        pending = await has_pending_bind_token(int(current_user.id))
        if pending:
            pending_purpose = await get_pending_pair_purpose(int(current_user.id))

    return DingtalkBindStatusResponse(
        linked=linked,
        mindbot_available=mindbot_available,
        dingtalk_staff_id=staff_masked,
        pending_token_active=pending,
        pending_pair_purpose=pending_purpose,
        token_ttl_seconds=BIND_TOKEN_TTL_SECONDS,
        rate_limited=not allowed,
    )


@router.post("/dingtalk-bind/cancel")
async def dingtalk_bind_cancel(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Revoke pending bind token when modal closes."""
    log_web_cancel(user_id=int(current_user.id))
    await revoke_pending_bind_token(int(current_user.id))
    return {"status": "ok"}


@router.post("/dingtalk-bind/unbind")
async def dingtalk_bind_unbind(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Direct unbind is disabled; use MindBot pair-code confirmation."""
    _ = current_user
    raise _bind_http_error(
        status.HTTP_410_GONE,
        "DINGTALK_BIND_USE_PAIR_UNBIND",
        "Use MindBot pair-code unbind flow from account settings",
    )
