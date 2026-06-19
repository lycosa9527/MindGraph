"""DingTalk QR bind API routes."""

from __future__ import annotations

import logging
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
from services.auth.dingtalk_bind_constants import (
    BIND_QUERY_CODE_PARAM,
    BIND_QUERY_PARAM,
    BIND_TOKEN_TTL_SECONDS,
)
from services.auth.dingtalk_bind_redis import (
    bind_code_secret_from_payload,
    get_bind_token_data,
    get_minter_bind_token,
    has_pending_bind_token,
    mint_bind_token,
    revoke_pending_bind_token,
    store_bind_token,
)
from services.auth.quick_register_room_code import (
    ROOM_CODE_PERIOD_SECONDS,
    current_room_code_from_room_secret,
)
from services.redis.rate_limiting.redis_rate_limiter import get_rate_limiter
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_BIND_MINT_MAX = 10
_BIND_MINT_WINDOW = 60
_BIND_STATUS_MAX = 120
_BIND_STATUS_WINDOW = 60
_BIND_UNBIND_MAX = 10
_BIND_UNBIND_WINDOW = 60
_BIND_QR_CODE_MAX = 120
_BIND_QR_CODE_WINDOW = 60


class DingtalkBindQrCodeResponse(BaseModel):
    """Rotating bind QR payload for modal polling."""

    code: str
    period_seconds: int = ROOM_CODE_PERIOD_SECONDS
    valid_until_unix: float
    ttl_seconds: int = BIND_TOKEN_TTL_SECONDS
    bind_token: str
    qr_query: str


class DingtalkBindStatusResponse(BaseModel):
    """Bind status for account modal polling."""

    linked: bool
    mindbot_available: bool
    dingtalk_staff_id: Optional[str] = None
    pending_token_active: bool = False
    token_ttl_seconds: int = Field(default=BIND_TOKEN_TTL_SECONDS)


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
    """Mint a single-use QR bind token for the current user."""
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
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_MINDBOT",
            "MindBot is not enabled for your organization",
        )

    token = mint_bind_token()
    stored = await store_bind_token(
        token=token,
        user_id=int(current_user.id),
        organization_id=int(org_id),
    )
    if not stored:
        raise _bind_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DINGTALK_BIND_REDIS_UNAVAILABLE",
            "Bind service temporarily unavailable",
        )

    return DingtalkBindStartResponse(token=token, ttl_seconds=BIND_TOKEN_TTL_SECONDS)


@router.get("/dingtalk-bind/qr-code", response_model=DingtalkBindQrCodeResponse)
async def dingtalk_bind_qr_code(
    bind_token: str | None = Query(default=None, min_length=20, max_length=512),
    current_user: User = Depends(get_current_user),
) -> DingtalkBindQrCodeResponse:
    """Return the current rotating 6-digit code and QR query string for the pending bind token."""
    limiter = get_rate_limiter()
    allowed, _, _ = await limiter.check_and_record(
        "dingtalk_bind_qr_code",
        f"user:{int(current_user.id)}",
        _BIND_QR_CODE_MAX,
        _BIND_QR_CODE_WINDOW,
    )
    if not allowed:
        raise _bind_http_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DINGTALK_BIND_RATE_LIMIT",
            "Too many QR refresh requests",
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
    if not isinstance(raw_user_id, int) and not (
        isinstance(raw_user_id, str) and str(raw_user_id).isdigit()
    ):
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
    qr_query = (
        f"{BIND_QUERY_PARAM}={channel_key}&{BIND_QUERY_CODE_PARAM}={code}"
    )
    return DingtalkBindQrCodeResponse(
        code=code,
        period_seconds=ROOM_CODE_PERIOD_SECONDS,
        valid_until_unix=float(next_start),
        ttl_seconds=BIND_TOKEN_TTL_SECONDS,
        bind_token=channel_key,
        qr_query=qr_query,
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
    if not allowed:
        raise _bind_http_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DINGTALK_BIND_RATE_LIMIT",
            "Too many status requests",
        )

    pending = await has_pending_bind_token(int(current_user.id))

    return DingtalkBindStatusResponse(
        linked=linked,
        mindbot_available=mindbot_available,
        dingtalk_staff_id=staff_masked,
        pending_token_active=pending,
        token_ttl_seconds=BIND_TOKEN_TTL_SECONDS,
    )


@router.post("/dingtalk-bind/cancel")
async def dingtalk_bind_cancel(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Revoke pending bind token when modal closes."""
    await revoke_pending_bind_token(int(current_user.id))
    return {"status": "ok"}


@router.post("/dingtalk-bind/unbind")
async def dingtalk_bind_unbind(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, str]:
    """Remove the current user's DingTalk staff link for their organization."""
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None or int(org_id) <= 0:
        raise _bind_http_error(
            status.HTTP_400_BAD_REQUEST,
            "DINGTALK_BIND_NO_ORG",
            "Organization membership required for DingTalk bind",
        )

    limiter = get_rate_limiter()
    allowed, _, _ = await limiter.check_and_record(
        "dingtalk_bind_unbind",
        f"user:{int(current_user.id)}",
        _BIND_UNBIND_MAX,
        _BIND_UNBIND_WINDOW,
    )
    if not allowed:
        raise _bind_http_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DINGTALK_BIND_RATE_LIMIT",
            "Too many unbind attempts",
        )

    repo = DingtalkStaffLinkRepository(db)
    removed = await repo.delete_for_user(int(org_id), int(current_user.id))
    if not removed:
        raise _bind_http_error(
            status.HTTP_404_NOT_FOUND,
            "DINGTALK_BIND_NOT_LINKED",
            "No DingTalk account is linked",
        )

    await db.commit()
    await revoke_pending_bind_token(int(current_user.id))
    logger.info(
        "[DingtalkBind] unbind_ok user_id=%s org_id=%s",
        int(current_user.id),
        int(org_id),
    )
    return {"status": "ok"}
