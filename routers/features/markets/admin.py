"""Admin-only market (市场) APIs."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from repositories.markets_repo import (
    MarketListingRepository,
    MarketOrderRepository,
    MarketSubscriptionRepository,
    MarketUserLookup,
)
from routers.auth.dependencies import require_admin
from routers.features.markets.helpers import require_markets_enabled

router = APIRouter()


class AdminOrderRow(BaseModel):
    id: int
    user_id: int
    user_email_or_phone: Optional[str]
    listing_id: int
    listing_title: str
    out_trade_no: str
    status: str
    amount_minor: int
    currency: str
    alipay_trade_no: Optional[str]
    created_at: str
    paid_at: Optional[str]


class AdminListingRow(BaseModel):
    id: int
    slug: str
    listing_kind: str
    title: str
    price_minor: int
    currency: str
    is_active: bool


class AdminSubscriptionRow(BaseModel):
    id: int
    user_id: int
    user_email_or_phone: Optional[str]
    listing_id: int
    listing_title: str
    alipay_agreement_id: Optional[str]
    status: str
    current_period_end: Optional[str]


@router.get("/admin/orders", response_model=list[AdminOrderRow])
async def admin_list_orders(
    status: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    _admin: User = Depends(require_admin),
) -> list[AdminOrderRow]:
    require_markets_enabled()
    repo = MarketOrderRepository(db)
    rows = await repo.admin_list(status=status, offset=offset, limit=limit)
    out: list[AdminOrderRow] = []
    for r in rows:
        email = await MarketUserLookup.get_email_or_phone(db, r.user_id)
        title = r.listing.title if r.listing else ""
        out.append(
            AdminOrderRow(
                id=r.id,
                user_id=r.user_id,
                user_email_or_phone=email,
                listing_id=r.listing_id,
                listing_title=title,
                out_trade_no=r.out_trade_no,
                status=r.status,
                amount_minor=r.amount_minor,
                currency=r.currency,
                alipay_trade_no=r.alipay_trade_no,
                created_at=r.created_at.isoformat() if r.created_at else "",
                paid_at=r.paid_at.isoformat() if r.paid_at else None,
            )
        )
    return out


@router.get("/admin/listings", response_model=list[AdminListingRow])
async def admin_list_listings(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
    _admin: User = Depends(require_admin),
) -> list[AdminListingRow]:
    require_markets_enabled()
    repo = MarketListingRepository(db)
    rows = await repo.get_all(offset=offset, limit=limit, order_by=[repo.model.id.asc()])
    return [
        AdminListingRow(
            id=r.id,
            slug=r.slug,
            listing_kind=r.listing_kind,
            title=r.title,
            price_minor=r.price_minor,
            currency=r.currency,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.get("/admin/subscriptions", response_model=list[AdminSubscriptionRow])
async def admin_list_subscriptions(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    _admin: User = Depends(require_admin),
) -> list[AdminSubscriptionRow]:
    require_markets_enabled()
    repo = MarketSubscriptionRepository(db)
    rows = await repo.admin_list(offset=offset, limit=limit)
    out: list[AdminSubscriptionRow] = []
    for r in rows:
        email = await MarketUserLookup.get_email_or_phone(db, r.user_id)
        title = r.listing.title if r.listing else ""
        out.append(
            AdminSubscriptionRow(
                id=r.id,
                user_id=r.user_id,
                user_email_or_phone=email,
                listing_id=r.listing_id,
                listing_title=title,
                alipay_agreement_id=r.alipay_agreement_id,
                status=r.status,
                current_period_end=r.current_period_end.isoformat() if r.current_period_end else None,
            )
        )
    return out


@router.get("/admin/stats", response_model=dict[str, Any])
async def admin_stats(
    db: AsyncSession = Depends(get_async_db),
    _admin: User = Depends(require_admin),
) -> dict[str, Any]:
    require_markets_enabled()
    orepo = MarketOrderRepository(db)
    total_orders = await orepo.count_admin()
    paid = await orepo.count_admin(status="paid")
    pending = await orepo.count_admin(status="pending")
    return {
        "orders_total": total_orders,
        "orders_paid": paid,
        "orders_pending": pending,
    }
