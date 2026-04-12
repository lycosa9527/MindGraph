"""Public market (市场) API: listings, orders, Alipay notify."""

import logging
import os
import secrets
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import User
from models.domain.markets import MarketListing, MarketOrder, MarketSubscription
from repositories.markets_repo import MarketListingRepository, MarketOrderRepository
from routers.auth.dependencies import get_current_user
from routers.features.markets.helpers import require_markets_enabled
from services.markets.alipay_page_pay import build_page_pay_form_html
from services.markets.alipay_settings import load_alipay_config
from services.markets.notify_process import apply_async_notify

logger = logging.getLogger(__name__)

router = APIRouter()


def _minor_to_yuan_str(price_minor: int) -> str:
    return f"{price_minor / 100.0:.2f}"


class ListingOut(BaseModel):
    id: int
    slug: str
    listing_kind: str
    title: str
    description: Optional[str]
    price_minor: int
    currency: str
    product_type: Optional[str]
    scene: Optional[str]
    subject: Optional[str]
    extra_json: Optional[dict[str, Any]]


class OrderCreateBody(BaseModel):
    listing_id: int = Field(ge=1)


class SubscriptionIntentBody(BaseModel):
    listing_id: int = Field(ge=1)


class OrderOut(BaseModel):
    id: int
    listing_id: int
    out_trade_no: str
    status: str
    amount_minor: int
    currency: str
    created_at: str


@router.get("/listings", response_model=list[ListingOut])
async def list_listings(
    listing_kind: Optional[str] = None,
    scene: Optional[str] = None,
    subject: Optional[str] = None,
    product_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> list[ListingOut]:
    require_markets_enabled()
    repo = MarketListingRepository(db)
    rows = await repo.list_active(
        listing_kind=listing_kind,
        scene=scene,
        subject=subject,
        product_type=product_type,
        offset=offset,
        limit=min(limit, 100),
    )
    return [
        ListingOut(
            id=r.id,
            slug=r.slug,
            listing_kind=r.listing_kind,
            title=r.title,
            description=r.description,
            price_minor=r.price_minor,
            currency=r.currency,
            product_type=r.product_type,
            scene=r.scene,
            subject=r.subject,
            extra_json=r.extra_json,
        )
        for r in rows
    ]


@router.post("/orders", response_model=OrderOut)
async def create_order(
    body: OrderCreateBody,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    require_markets_enabled()
    listing = await db.get(MarketListing, body.listing_id)
    if listing is None or not listing.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.listing_kind == "subscription_plan":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use subscription endpoint for subscription_plan listings",
        )

    out_trade_no = f"MG{user.id}{secrets.token_hex(12)}"[:64]
    order = MarketOrder(
        user_id=user.id,
        listing_id=listing.id,
        out_trade_no=out_trade_no,
        status="pending",
        amount_minor=listing.price_minor,
        currency=listing.currency,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return OrderOut(
        id=order.id,
        listing_id=order.listing_id,
        out_trade_no=order.out_trade_no,
        status=order.status,
        amount_minor=order.amount_minor,
        currency=order.currency,
        created_at=order.created_at.isoformat() if order.created_at else "",
    )


@router.post("/orders/{order_id}/pay", response_class=HTMLResponse)
async def pay_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return auto-submit HTML form to Alipay (PC page pay)."""
    require_markets_enabled()
    cfg = load_alipay_config()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alipay is not configured (ALIPAY_APP_ID / keys)",
        )
    if not cfg.notify_base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ALIPAY_NOTIFY_BASE_URL is required for async notify",
        )

    orepo = MarketOrderRepository(db)
    order = await orepo.get_by_id(order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not payable")

    listing = await db.get(MarketListing, order.listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing missing")

    notify_url = f"{cfg.notify_base_url.rstrip('/')}/api/markets/payments/alipay/notify"
    return_url = ""
    external = os.getenv("EXTERNAL_BASE_URL", "").strip().rstrip("/")
    if external:
        return_url = f"{external}/template"

    html = build_page_pay_form_html(
        cfg=cfg,
        out_trade_no=order.out_trade_no,
        total_amount_yuan=_minor_to_yuan_str(order.amount_minor),
        subject=listing.title[:128],
        notify_url=notify_url,
        return_url=return_url or None,
    )
    return HTMLResponse(content=html)


@router.get("/orders", response_model=list[OrderOut])
async def my_orders(
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = 50,
) -> list[OrderOut]:
    require_markets_enabled()
    repo = MarketOrderRepository(db)
    rows = await repo.list_for_user(user.id, offset=offset, limit=min(limit, 100))
    return [
        OrderOut(
            id=r.id,
            listing_id=r.listing_id,
            out_trade_no=r.out_trade_no,
            status=r.status,
            amount_minor=r.amount_minor,
            currency=r.currency,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.post("/subscriptions/intent")
async def subscription_intent(
    body: SubscriptionIntentBody,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a pending subscription row; Alipay periodic agreement is completed in a follow-up."""
    require_markets_enabled()
    listing = await db.get(MarketListing, body.listing_id)
    if listing is None or not listing.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.listing_kind != "subscription_plan":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing is not a subscription_plan",
        )
    sub = MarketSubscription(user_id=user.id, listing_id=listing.id, status="pending")
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return {
        "id": sub.id,
        "status": sub.status,
        "message": "Subscription intent recorded; complete Alipay agreement signing when merchant product is enabled.",
    }


@router.post("/payments/alipay/notify", response_class=PlainTextResponse)
async def alipay_notify(request: Request, db: AsyncSession = Depends(get_async_db)) -> PlainTextResponse:
    """Alipay async notification (unsigned route; signature verified inside)."""
    if not config.FEATURE_MARKETS:
        return PlainTextResponse("fail")
    cfg = load_alipay_config()
    if cfg is None:
        logger.error("[Markets] Notify received but Alipay not configured")
        return PlainTextResponse("fail", status_code=503)

    form = await request.form()
    params: dict[str, Any] = dict(form)
    try:
        result = await apply_async_notify(db, params, cfg)
    except Exception:
        logger.exception("[Markets] Notify processing failed")
        await db.rollback()
        return PlainTextResponse("fail")
    return PlainTextResponse(result)
