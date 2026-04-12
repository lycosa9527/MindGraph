"""Apply Alipay async notify after signature verification."""

from datetime import UTC, datetime
import logging
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.markets import MarketEntitlement, MarketPayment
from repositories.markets_repo import MarketEntitlementRepository, MarketOrderRepository, MarketPaymentRepository
from services.markets.alipay_notify import verify_async_notify
from services.markets.alipay_settings import AlipayEnvConfig

logger = logging.getLogger(__name__)


def _get_str(data: Mapping[str, Any], key: str) -> str | None:
    raw = data.get(key)
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and raw:
        return str(raw[0])
    return str(raw)


async def apply_async_notify(
    session: AsyncSession,
    params: Mapping[str, Any],
    cfg: AlipayEnvConfig,
) -> str:
    """Verify signature and update order; return ``success`` or ``fail`` for Alipay."""
    if not verify_async_notify(params, cfg.alipay_public_key):
        logger.warning("[Markets] Notify rejected: bad signature")
        return "fail"

    out_trade_no = _get_str(params, "out_trade_no")
    trade_status = _get_str(params, "trade_status")
    trade_no = _get_str(params, "trade_no")
    notify_id = _get_str(params, "notify_id") or trade_no

    if not out_trade_no:
        logger.warning("[Markets] Notify missing out_trade_no")
        return "fail"

    order_repo = MarketOrderRepository(session)
    pay_repo = MarketPaymentRepository(session)
    ent_repo = MarketEntitlementRepository(session)

    order = await order_repo.get_by_out_trade_no(out_trade_no)
    if order is None:
        logger.warning("[Markets] Notify unknown out_trade_no=%s", out_trade_no)
        return "fail"

    if order.status == "paid":
        return "success"

    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        return "success"

    if notify_id:
        existing = await pay_repo.get_by_notify_id(notify_id)
        if existing is not None:
            return "success"

    now = datetime.now(UTC)
    order.status = "paid"
    order.alipay_trade_no = trade_no
    order.paid_at = now.replace(tzinfo=None)

    payment = MarketPayment(order_id=order.id, notify_id=notify_id, trade_no=trade_no)
    session.add(payment)

    if not await ent_repo.has_entitlement(order.user_id, order.listing_id):
        session.add(
            MarketEntitlement(
                user_id=order.user_id,
                listing_id=order.listing_id,
                order_id=order.id,
                expires_at=None,
            )
        )

    await session.commit()
    return "success"
