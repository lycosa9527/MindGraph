"""User-facing thinking coin wallet API."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from services.auth.thinking_coin.checkin_service import ensure_wallet_bootstrap
from services.auth.thinking_coin.event_hub import mutation_to_footer, track_checkin, track_client_event
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
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
    items = [
        LedgerItem(
            id=row.id,
            delta=int(row.delta),
            balance_after=int(row.balance_after),
            reason=str(row.reason),
            ref_type=row.ref_type,
            ref_id=row.ref_id,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]
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
