"""Grant and query user entitlements for Markets B2C access."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.markets import MarketEntitlement, MarketListing
from repositories.markets_repo import MarketEntitlementRepository


def entitlement_expires_from_listing(listing: MarketListing, *, paid_at: datetime) -> Optional[datetime]:
    """Compute expiry for one-time SKUs with ``access_days`` in ``extra_json``."""
    extra = listing.extra_json or {}
    access_days = extra.get("access_days")
    if isinstance(access_days, int) and access_days > 0:
        return paid_at + timedelta(days=access_days)
    if isinstance(access_days, str) and access_days.isdigit():
        return paid_at + timedelta(days=int(access_days))
    return None


async def grant_or_extend_entitlement(
    session: AsyncSession,
    *,
    user_id: int,
    listing_id: int,
    expires_at: Optional[datetime],
    order_id: Optional[int] = None,
    subscription_id: Optional[int] = None,
) -> MarketEntitlement:
    """Grant or extend entitlement."""
    repo = MarketEntitlementRepository(session)
    existing = await repo.get_for_user_listing(user_id, listing_id)
    if existing is None:
        row = MarketEntitlement(
            user_id=user_id,
            listing_id=listing_id,
            order_id=order_id,
            subscription_id=subscription_id,
            expires_at=expires_at,
        )
        session.add(row)
        return row

    if order_id is not None:
        existing.order_id = order_id
    if subscription_id is not None:
        existing.subscription_id = subscription_id
    if expires_at is None:
        existing.expires_at = None
    elif existing.expires_at is None or expires_at > existing.expires_at:
        existing.expires_at = expires_at
    return existing


async def user_has_active_entitlement(session: AsyncSession, user_id: int, listing_id: int) -> bool:
    """User has active entitlement."""
    repo = MarketEntitlementRepository(session)
    row = await repo.get_for_user_listing(user_id, listing_id)
    return repo.is_row_active(row)


async def list_active_entitlements(session: AsyncSession, user_id: int) -> Sequence[MarketEntitlement]:
    """List active entitlements."""
    repo = MarketEntitlementRepository(session)
    return await repo.list_active_for_user(user_id)


def entitlement_to_dict(row: MarketEntitlement, listing: Optional[MarketListing]) -> dict[str, Any]:
    """Entitlement to dict."""
    return {
        "listing_id": row.listing_id,
        "listing_slug": listing.slug if listing else None,
        "listing_title": listing.title if listing else None,
        "listing_kind": listing.listing_kind if listing else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "subscription_id": row.subscription_id,
        "order_id": row.order_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
