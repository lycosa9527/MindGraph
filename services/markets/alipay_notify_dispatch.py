"""Route Alipay async notifications to trade or agreement handlers."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from services.markets.agreement_notify_process import apply_agreement_notify
from services.markets.alipay_common import get_notify_str
from services.markets.alipay_settings import AlipayEnvConfig
from services.markets.notify_process import apply_trade_notify

_AGREEMENT_NOTIFY_TYPES = frozenset({"dut_user_sign", "dut_user_unsign"})


async def dispatch_alipay_notify(
    session: AsyncSession,
    params: Mapping[str, Any],
    cfg: AlipayEnvConfig,
) -> str:
    notify_type = (get_notify_str(params, "notify_type") or "").lower()
    if notify_type in _AGREEMENT_NOTIFY_TYPES:
        return await apply_agreement_notify(session, params, cfg)
    return await apply_trade_notify(session, params, cfg)
