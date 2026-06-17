"""
Apply Alipay agreement lifecycle async notifications.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.markets_repo import MarketSubscriptionRepository
from services.markets.alipay_common import get_notify_str, utc_now_naive, verify_notify_app_id
from services.markets.alipay_notify import verify_async_notify
from services.markets.alipay_settings import AlipayEnvConfig
from services.markets.entitlement_service import grant_or_extend_entitlement
from services.markets.subscription_service import subscription_period_end

logger = logging.getLogger(__name__)


async def apply_agreement_notify(
    session: AsyncSession,
    params: Mapping[str, Any],
    cfg: AlipayEnvConfig,
) -> str:
    """Apply agreement notify."""
    if not verify_async_notify(params, cfg.alipay_public_key):
        logger.warning("[Markets] Agreement notify rejected: bad signature")
        return "fail"
    if not verify_notify_app_id(params, cfg):
        logger.warning("[Markets] Agreement notify rejected: app_id mismatch")
        return "fail"

    notify_type = (get_notify_str(params, "notify_type") or "").lower()
    if notify_type == "dut_user_sign":
        return await _apply_user_sign(session, params)
    if notify_type == "dut_user_unsign":
        return await _apply_user_unsign(session, params)
    logger.warning("[Markets] Agreement notify ignored: notify_type=%s", notify_type)
    return "success"


async def _apply_user_sign(session: AsyncSession, params: Mapping[str, Any]) -> str:
    """Apply user sign."""
    status = (get_notify_str(params, "status") or "").upper()
    if status and status != "NORMAL":
        return "success"

    external_agreement_no = get_notify_str(params, "external_agreement_no")
    agreement_no = get_notify_str(params, "agreement_no")
    if not external_agreement_no or not agreement_no:
        logger.warning("[Markets] Agreement sign notify missing ids")
        return "fail"

    repo = MarketSubscriptionRepository(session)
    sub = await repo.get_by_external_agreement_no(external_agreement_no)
    if sub is None:
        logger.warning("[Markets] Agreement sign unknown external_agreement_no=%s", external_agreement_no)
        return "fail"
    if sub.status == "active" and sub.alipay_agreement_id == agreement_no:
        return "success"

    now = utc_now_naive()
    sub.alipay_agreement_id = agreement_no
    sub.status = "active"
    sub.started_at = sub.started_at or now
    sub.current_period_end = subscription_period_end(sub.listing, start=now)

    await grant_or_extend_entitlement(
        session,
        user_id=sub.user_id,
        listing_id=sub.listing_id,
        expires_at=sub.current_period_end,
        subscription_id=sub.id,
    )
    await session.commit()
    return "success"


async def _apply_user_unsign(session: AsyncSession, params: Mapping[str, Any]) -> str:
    """Apply user unsign."""
    agreement_no = get_notify_str(params, "agreement_no")
    external_agreement_no = get_notify_str(params, "external_agreement_no")
    repo = MarketSubscriptionRepository(session)
    sub = None
    if agreement_no:
        sub = await repo.get_by_agreement_id(agreement_no)
    if sub is None and external_agreement_no:
        sub = await repo.get_by_external_agreement_no(external_agreement_no)
    if sub is None:
        logger.warning("[Markets] Agreement unsign unknown agreement")
        return "fail"
    if sub.status == "cancelled":
        return "success"

    sub.status = "cancelled"
    sub.cancelled_at = utc_now_naive()
    await session.commit()
    return "success"
