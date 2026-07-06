"""User-facing thinking coin wallet API."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.auth.thinking_coin.checkin_service import ensure_wallet_bootstrap
from services.auth.thinking_coin.school_consult_validation import (
    NAME_MAX_LEN,
    NOTE_MAX_LEN,
    ORG_MAX_LEN,
    PHONE_MAX_LEN,
    sanitize_consult_field,
    validate_consult_phone,
)
from services.auth.thinking_coin.school_consult_notify import (
    map_notify_result_to_http_status,
    send_school_consult_notification,
)
from services.auth.thinking_coin.event_hub import mutation_to_footer, track_checkin, track_client_event
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.ledger_enrichment import collect_earn_task_ids, load_earn_tasks_by_ids
from services.auth.thinking_coin.ledger_queries import fetch_ledger_page
from services.auth.thinking_coin.wallet_payload import build_wallet_payload
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth import get_current_user
from utils.auth.thinking_coin_config import feature_thinking_coins_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/thinking-coins", tags=["thinking-coins"])


class LedgerItem(BaseModel):
    """One ledger row in API responses."""

    id: int
    delta: int
    balance_after: int
    reason: str
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    task_title: Optional[str] = None
    task_title_en: Optional[str] = None
    created_at: str


class LedgerResponse(BaseModel):
    """Paginated ledger payload."""

    items: list[LedgerItem]
    total: int
    page: int
    limit: int


async def _load_org(user: User):
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return None
    try:
        return await org_cache.get_by_id(int(org_id))
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[ThinkingCoins] org cache failed: %s", exc)
        return None


@router.get("/wallet")
async def get_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Balance and active earn tasks."""
    if not feature_thinking_coins_enabled():
        return {"balance": 0, "eligible": False, "earn_tasks": []}

    org = await _load_org(current_user)
    if user_eligible_for_thinking_coins(current_user, org):
        await ensure_wallet_bootstrap(db, current_user, org)
    return await build_wallet_payload(db, current_user, org)


@router.get("/ledger", response_model=LedgerResponse)
async def get_ledger(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> LedgerResponse:
    """Paginated thinking coin transaction history."""
    org = await _load_org(current_user)
    if not user_eligible_for_thinking_coins(current_user, org):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not eligible")

    rows, total = await fetch_ledger_page(db, int(current_user.id), page=page, limit=limit)
    earn_tasks_by_id = await load_earn_tasks_by_ids(db, collect_earn_task_ids(rows))
    items = []
    for row in rows:
        task_title: str | None = None
        task_title_en: str | None = None
        if row.ref_type == "earn_task" and row.ref_id:
            try:
                earn_task = earn_tasks_by_id.get(int(str(row.ref_id).strip()))
            except ValueError:
                earn_task = None
            if earn_task is not None:
                task_title = earn_task.title
                task_title_en = earn_task.title_en
        items.append(
            LedgerItem(
                id=row.id,
                delta=int(row.delta),
                balance_after=int(row.balance_after),
                reason=str(row.reason),
                ref_type=row.ref_type,
                ref_id=row.ref_id,
                task_title=task_title,
                task_title_en=task_title_en,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
        )
    return LedgerResponse(items=items, total=total, page=page, limit=limit)


class CheckInResponse(BaseModel):
    """Daily check-in result."""

    credited: int = Field(description="Coins credited this call (0 if already checked in)")
    balance: int
    thinking_coins: Optional[dict[str, Any]] = None


class ClaimEventBody(BaseModel):
    """Client-side product exploration event."""

    event_key: str = Field(min_length=1, max_length=64)


class ClaimEventResponse(BaseModel):
    """Client event claim result."""

    credited: int
    balance: int
    slug: Optional[str] = None
    thinking_coins: Optional[dict[str, Any]] = None


@router.post("/check-in", response_model=CheckInResponse)
async def post_check_in(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> CheckInResponse:
    """Explicit daily check-in (also runs on login via /wallet bootstrap)."""
    org = await _load_org(current_user)
    if not user_eligible_for_thinking_coins(current_user, org):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not eligible")

    mutation = await track_checkin(db, current_user, org)
    footer = mutation_to_footer(mutation)
    return CheckInResponse(
        credited=mutation.credited,
        balance=mutation.balance,
        thinking_coins=footer if mutation.eligible else None,
    )


@router.post("/claim-event", response_model=ClaimEventResponse)
async def post_claim_event(
    body: ClaimEventBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ClaimEventResponse:
    """Credit once-per-day reward after a client-side exploration action."""
    if not feature_thinking_coins_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enabled")

    org = await _load_org(current_user)
    if not user_eligible_for_thinking_coins(current_user, org):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not eligible")

    mutation = await track_client_event(db, current_user, org, body.event_key)
    footer = mutation_to_footer(mutation)
    return ClaimEventResponse(
        credited=mutation.credited,
        balance=mutation.balance,
        slug=mutation.task_slug,
        thinking_coins=footer if mutation.eligible else None,
    )


class SchoolConsultationBody(BaseModel):
    """School-tier consultation form submission."""

    name: str = Field(min_length=1, max_length=NAME_MAX_LEN)
    phone: str = Field(min_length=1, max_length=PHONE_MAX_LEN)
    organization: str = Field(min_length=1, max_length=ORG_MAX_LEN)
    note: str = Field(default="", max_length=NOTE_MAX_LEN)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Sanitize display name before outbound WeCom markdown."""
        return sanitize_consult_field(value, max_len=NAME_MAX_LEN)

    @field_validator("organization")
    @classmethod
    def validate_organization(cls, value: str) -> str:
        """Sanitize organization name before outbound WeCom markdown."""
        return sanitize_consult_field(value, max_len=ORG_MAX_LEN)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Reject malformed contact numbers."""
        return validate_consult_phone(value)

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        """Optional note — allow short multiline, still sanitized."""
        trimmed = value.strip()
        if not trimmed:
            return ""
        return sanitize_consult_field(trimmed, max_len=NOTE_MAX_LEN, keep_newlines=True)


class SchoolConsultationResponse(BaseModel):
    """Acknowledgement for a delivered consultation request."""

    ok: bool = True


@router.post("/school-consultation", response_model=SchoolConsultationResponse)
async def post_school_consultation(
    body: SchoolConsultationBody,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> SchoolConsultationResponse:
    """Forward school consultation inquiry to configured WeCom destinations."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "school_consultation",
        identifier,
        max_requests=3,
        window_seconds=3600,
    )

    org = await _load_org(current_user)
    org_name: str | None = None
    if org is not None:
        org_name_raw = getattr(org, "name", None)
        if isinstance(org_name_raw, str) and org_name_raw.strip():
            org_name = org_name_raw.strip()

    note = body.note or None
    result = await send_school_consult_notification(
        name=body.name,
        phone=body.phone,
        organization=body.organization,
        note=note,
        user=current_user,
        org_name=org_name,
    )
    status_code, detail = map_notify_result_to_http_status(result)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=detail)
    return SchoolConsultationResponse(ok=True)
