"""Public market (市场) API: listings, orders, Alipay notify."""

import logging
import os
import secrets
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import User
from models.domain.markets import MarketListing, MarketOrder, MarketSubscription
from repositories.markets_repo import MarketListingRepository, MarketOrderRepository, MarketSubscriptionRepository
from routers.api.helpers import normalize_external_base_url
from routers.auth.dependencies import get_current_user
from routers.features.markets.helpers import require_markets_enabled
from services.markets.alipay_agreement_sign import build_agreement_sign_form_html
from services.markets.alipay_agreement_unsign import unsign_agreement
from services.markets.alipay_common import minor_to_yuan_str, trade_notify_url, utc_now_naive
from services.markets.alipay_notify_dispatch import dispatch_alipay_notify
from services.markets.alipay_page_pay import build_page_pay_form_html
from services.markets.alipay_settings import AlipayEnvConfig, load_alipay_config
from services.markets.entitlement_service import entitlement_to_dict, list_active_entitlements
from services.markets.subscription_service import (
    get_or_create_subscription_intent,
    subscription_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_alipay_config() -> AlipayEnvConfig:
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
    return cfg


def _user_external_logon_id(user: User) -> str:
    if user.email:
        return str(user.email)
    if user.phone:
        return str(user.phone)
    return f"mg_user_{user.id}"


def _subscription_return_url() -> str | None:
    external = normalize_external_base_url(os.getenv("EXTERNAL_BASE_URL", ""))
    if external:
        return f"{external}/template"
    return None


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
    subscription_id: Optional[int] = None
    created_at: str


class SubscriptionOut(BaseModel):
    id: int
    listing_id: int
    listing_slug: Optional[str]
    listing_title: Optional[str]
    status: str
    external_agreement_no: Optional[str]
    alipay_agreement_id: Optional[str]
    current_period_end: Optional[str]
    started_at: Optional[str]
    cancelled_at: Optional[str]
    created_at: str
    billing: Optional[dict[str, Any]] = None


class EntitlementOut(BaseModel):
    listing_id: int
    listing_slug: Optional[str]
    listing_title: Optional[str]
    listing_kind: Optional[str]
    expires_at: Optional[str]
    subscription_id: Optional[int]
    order_id: Optional[int]
    created_at: Optional[str]


@router.get("/listings", response_model=list[ListingOut])
async def list_listings(
    response: Response,
    listing_kind: Optional[str] = None,
    scene: Optional[str] = None,
    subject: Optional[str] = None,
    product_type: Optional[str] = None,
    after_id: Optional[int] = Query(
        None,
        ge=1,
        description="Keyset cursor: id of the last row from the previous page.",
    ),
    offset: int = Query(0, ge=0, description="Legacy offset; ignored when after_id is supplied."),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> list[ListingOut]:
    require_markets_enabled()
    repo = MarketListingRepository(db)
    rows = await repo.list_active(
        listing_kind=listing_kind,
        scene=scene,
        subject=subject,
        product_type=product_type,
        after_id=after_id,
        offset=offset,
        limit=limit,
    )
    if rows and len(rows) == limit:
        response.headers["X-Next-Cursor"] = str(rows[-1].id)
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
        subscription_id=order.subscription_id,
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
    cfg = _require_alipay_config()

    orepo = MarketOrderRepository(db)
    order = await orepo.get_by_id(order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not payable")

    listing = await db.get(MarketListing, order.listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing missing")

    html = build_page_pay_form_html(
        cfg=cfg,
        out_trade_no=order.out_trade_no,
        total_amount_yuan=minor_to_yuan_str(order.amount_minor),
        subject=listing.title[:128],
        notify_url=trade_notify_url(cfg),
        return_url=_subscription_return_url(),
    )
    return HTMLResponse(content=html)


@router.get("/orders", response_model=list[OrderOut])
async def my_orders(
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
    before_id: Optional[int] = Query(
        None,
        ge=1,
        description="Keyset cursor: id of the last row from the previous page.",
    ),
    offset: int = Query(0, ge=0, description="Legacy offset; ignored when before_id is supplied."),
    limit: int = Query(50, ge=1, le=100),
) -> list[OrderOut]:
    require_markets_enabled()
    repo = MarketOrderRepository(db)
    rows = await repo.list_for_user(
        user.id,
        before_id=before_id,
        offset=offset,
        limit=limit,
    )
    if rows and len(rows) == limit:
        response.headers["X-Next-Cursor"] = str(rows[-1].id)
    return [
        OrderOut(
            id=r.id,
            listing_id=r.listing_id,
            out_trade_no=r.out_trade_no,
            status=r.status,
            amount_minor=r.amount_minor,
            currency=r.currency,
            subscription_id=r.subscription_id,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/entitlements", response_model=list[EntitlementOut])
async def my_entitlements(
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> list[EntitlementOut]:
    require_markets_enabled()
    rows = await list_active_entitlements(db, user.id)
    return [EntitlementOut(**entitlement_to_dict(row, row.listing)) for row in rows]


@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def my_subscriptions(
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> list[SubscriptionOut]:
    require_markets_enabled()
    repo = MarketSubscriptionRepository(db)
    rows = await repo.list_for_user(user.id)
    return [SubscriptionOut(**subscription_to_dict(row)) for row in rows]


@router.post("/subscriptions/intent", response_model=SubscriptionOut)
async def subscription_intent(
    body: SubscriptionIntentBody,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> SubscriptionOut:
    """Create or reuse a pending subscription for a monthly plan SKU."""
    require_markets_enabled()
    listing = await db.get(MarketListing, body.listing_id)
    if listing is None or not listing.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.listing_kind != "subscription_plan":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing is not a subscription_plan",
        )
    sub = await get_or_create_subscription_intent(db, user=user, listing=listing)
    await db.commit()
    await db.refresh(sub)
    return SubscriptionOut(**subscription_to_dict(sub))


@router.post("/subscriptions/{subscription_id}/sign", response_class=HTMLResponse)
async def sign_subscription(
    subscription_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return auto-submit HTML form for Alipay periodic agreement signing."""
    require_markets_enabled()
    cfg = _require_alipay_config()
    sub = await db.get(MarketSubscription, subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if sub.status not in ("pending", "past_due"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subscription is not signable")

    listing = await db.get(MarketListing, sub.listing_id)
    if listing is None or listing.listing_kind != "subscription_plan":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing missing")

    if not sub.external_agreement_no:
        sub.external_agreement_no = f"MGSub{user.id}{secrets.token_hex(8)}"[:64]
        await db.commit()
        await db.refresh(sub)

    html = build_agreement_sign_form_html(
        cfg=cfg,
        subscription=sub,
        listing=listing,
        external_logon_id=_user_external_logon_id(user),
        notify_url=trade_notify_url(cfg),
        return_url=_subscription_return_url(),
    )
    return HTMLResponse(content=html)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionOut)
async def cancel_subscription(
    subscription_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> SubscriptionOut:
    """Cancel a subscription and unsign the Alipay agreement when present."""
    require_markets_enabled()
    sub = await db.get(MarketSubscription, subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if sub.status == "cancelled":
        return SubscriptionOut(**subscription_to_dict(sub))

    if sub.alipay_agreement_id:
        cfg = load_alipay_config()
        if cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Alipay is not configured",
            )
        try:
            unsign_agreement(cfg=cfg, agreement_no=sub.alipay_agreement_id)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    sub.status = "cancelled"
    sub.cancelled_at = utc_now_naive()
    await db.commit()
    await db.refresh(sub)
    return SubscriptionOut(**subscription_to_dict(sub))


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
        result = await dispatch_alipay_notify(db, params, cfg)
    except Exception:
        logger.exception("[Markets] Notify processing failed")
        await db.rollback()
        return PlainTextResponse("fail")
    return PlainTextResponse(result)
