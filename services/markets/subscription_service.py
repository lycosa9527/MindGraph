"""
B2C subscription lifecycle helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import secrets
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.markets import MarketListing, MarketSubscription
from repositories.markets_repo import MarketSubscriptionRepository
from services.markets.alipay_agreement_sign import listing_sign_metadata
from services.markets.alipay_common import add_billing_period, listing_billing_interval, utc_now_naive


def build_external_agreement_no(user_id: int) -> str:
    """Build external agreement no."""
    token = secrets.token_hex(8)
    return f"MGSub{user_id}{token}"[:64]


async def get_or_create_subscription_intent(
    session: AsyncSession,
    *,
    user: User,
    listing: MarketListing,
) -> MarketSubscription:
    """Get or create subscription intent."""
    repo = MarketSubscriptionRepository(session)
    existing = await repo.get_open_for_user_listing(user.id, listing.id)
    if existing is not None:
        if existing.external_agreement_no is None:
            existing.external_agreement_no = build_external_agreement_no(user.id)
        return existing

    sub = MarketSubscription(
        user_id=user.id,
        listing_id=listing.id,
        status="pending",
        external_agreement_no=build_external_agreement_no(user.id),
    )
    session.add(sub)
    await session.flush()
    return sub


def subscription_period_end(listing: MarketListing, *, start: Optional[Any] = None) -> Any:
    """Subscription period end."""
    base = start if start is not None else utc_now_naive()
    interval = listing_billing_interval(listing.extra_json)
    return add_billing_period(base, interval)


def subscription_to_dict(sub: MarketSubscription) -> dict[str, Any]:
    """Subscription to dict."""
    listing = sub.listing
    return {
        "id": sub.id,
        "listing_id": sub.listing_id,
        "listing_slug": listing.slug if listing else None,
        "listing_title": listing.title if listing else None,
        "status": sub.status,
        "external_agreement_no": sub.external_agreement_no,
        "alipay_agreement_id": sub.alipay_agreement_id,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "started_at": sub.started_at.isoformat() if sub.started_at else None,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "billing": listing_sign_metadata(listing) if listing else None,
    }
