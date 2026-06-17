"""Apply Alipay async notify after signature verification."""

from __future__ import annotations

import logging
import secrets
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.markets import MarketOrder, MarketPayment
from repositories.markets_repo import (
    MarketOrderRepository,
    MarketPaymentRepository,
    MarketSubscriptionRepository,
)
from services.markets.alipay_common import (
    get_notify_str,
    utc_now_naive,
    verify_notify_amount,
    verify_notify_app_id,
)
from services.markets.alipay_notify import verify_async_notify
from services.markets.alipay_settings import AlipayEnvConfig
from services.markets.entitlement_service import entitlement_expires_from_listing, grant_or_extend_entitlement
from services.markets.subscription_service import subscription_period_end

logger = logging.getLogger(__name__)


async def apply_trade_notify(
    session: AsyncSession,
    params: Mapping[str, Any],
    cfg: AlipayEnvConfig,
) -> str:
    """Verify signature and update order/subscription; return ``success`` or ``fail``."""
    if not verify_async_notify(params, cfg.alipay_public_key):
        logger.warning("[Markets] Notify rejected: bad signature")
        return "fail"
    if not verify_notify_app_id(params, cfg):
        logger.warning("[Markets] Notify rejected: app_id mismatch")
        return "fail"

    out_trade_no = get_notify_str(params, "out_trade_no")
    trade_status = get_notify_str(params, "trade_status")
    trade_no = get_notify_str(params, "trade_no")
    notify_id = get_notify_str(params, "notify_id") or trade_no
    total_amount = get_notify_str(params, "total_amount")

    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return "success"

    order_repo = MarketOrderRepository(session)
    pay_repo = MarketPaymentRepository(session)

    order = await order_repo.get_by_out_trade_no(out_trade_no) if out_trade_no else None
    if order is None:
        return await _apply_subscription_renewal_notify(
            session,
            params,
            pay_repo=pay_repo,
            notify_id=notify_id,
            trade_no=trade_no,
            total_amount=total_amount,
        )

    if order.status == "paid":
        return "success"

    if not verify_notify_amount(total_amount, order.amount_minor):
        logger.warning(
            "[Markets] Notify amount mismatch out_trade_no=%s expected=%s got=%s",
            out_trade_no,
            order.amount_minor,
            total_amount,
        )
        return "fail"

    if notify_id:
        existing = await pay_repo.get_by_notify_id(notify_id)
        if existing is not None:
            return "success"

    now = utc_now_naive()
    order.status = "paid"
    order.alipay_trade_no = trade_no
    order.paid_at = now

    payment = MarketPayment(order_id=order.id, notify_id=notify_id, trade_no=trade_no)
    session.add(payment)

    listing = order.listing
    expires_at = entitlement_expires_from_listing(listing, paid_at=now) if listing else None
    await grant_or_extend_entitlement(
        session,
        user_id=order.user_id,
        listing_id=order.listing_id,
        expires_at=expires_at,
        order_id=order.id,
        subscription_id=order.subscription_id,
    )

    if order.subscription_id is not None:
        sub_repo = MarketSubscriptionRepository(session)
        sub = await sub_repo.get_by_id(order.subscription_id)
        if sub is not None and listing is not None:
            sub.status = "active"
            sub.current_period_end = subscription_period_end(listing, start=now)

    await session.commit()
    return "success"


async def _apply_subscription_renewal_notify(
    session: AsyncSession,
    params: Mapping[str, Any],
    *,
    pay_repo: MarketPaymentRepository,
    notify_id: str | None,
    trade_no: str | None,
    total_amount: str | None,
) -> str:
    """Apply subscription renewal notify."""
    agreement_no = get_notify_str(params, "agreement_no")
    if not agreement_no:
        out_trade_no = get_notify_str(params, "out_trade_no")
        logger.warning("[Markets] Notify unknown out_trade_no=%s", out_trade_no)
        return "fail"

    sub_repo = MarketSubscriptionRepository(session)
    sub = await sub_repo.get_by_agreement_id(agreement_no)
    if sub is None:
        logger.warning("[Markets] Renewal notify unknown agreement_no=%s", agreement_no)
        return "fail"

    listing = sub.listing
    if listing is None:
        return "fail"
    if not verify_notify_amount(total_amount, listing.price_minor):
        logger.warning(
            "[Markets] Renewal amount mismatch agreement_no=%s expected=%s got=%s",
            agreement_no,
            listing.price_minor,
            total_amount,
        )
        return "fail"

    if notify_id:
        existing = await pay_repo.get_by_notify_id(notify_id)
        if existing is not None:
            return "success"

    out_trade_no = get_notify_str(params, "out_trade_no") or f"MGSubPay{sub.id}{secrets.token_hex(8)}"[:64]
    order_repo = MarketOrderRepository(session)
    existing_order = await order_repo.get_by_out_trade_no(out_trade_no)
    if existing_order is not None and existing_order.status == "paid":
        return "success"

    now = utc_now_naive()
    if existing_order is None:
        order = MarketOrder(
            user_id=sub.user_id,
            listing_id=sub.listing_id,
            subscription_id=sub.id,
            out_trade_no=out_trade_no,
            status="paid",
            amount_minor=listing.price_minor,
            currency=listing.currency,
            alipay_trade_no=trade_no,
            paid_at=now,
        )
        session.add(order)
        await session.flush()
    else:
        order = existing_order
        order.status = "paid"
        order.alipay_trade_no = trade_no
        order.paid_at = now

    payment = MarketPayment(order_id=order.id, notify_id=notify_id, trade_no=trade_no)
    session.add(payment)

    period_end = subscription_period_end(listing, start=sub.current_period_end or now)
    sub.status = "active"
    sub.current_period_end = period_end
    await grant_or_extend_entitlement(
        session,
        user_id=sub.user_id,
        listing_id=sub.listing_id,
        expires_at=period_end,
        order_id=order.id,
        subscription_id=sub.id,
    )
    await session.commit()
    return "success"
