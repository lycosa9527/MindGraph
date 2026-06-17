"""
Build Alipay periodic agreement sign page (B2C subscription).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Optional

from alipay.aop.api.domain.AlipayUserAgreementPageSignModel import AlipayUserAgreementPageSignModel
from alipay.aop.api.domain.PeriodRuleParams import PeriodRuleParams
from alipay.aop.api.request.AlipayUserAgreementPageSignRequest import AlipayUserAgreementPageSignRequest

from models.domain.markets import MarketListing, MarketSubscription
from services.markets.alipay_client import build_alipay_client
from services.markets.alipay_common import (
    listing_billing_interval,
    listing_execute_time,
    minor_to_yuan_str,
)
from services.markets.alipay_settings import AlipayEnvConfig


def _resolve_sign_scene(cfg: AlipayEnvConfig, listing: MarketListing) -> str:
    """Resolve sign scene."""
    extra = listing.extra_json or {}
    scene = extra.get("sign_scene")
    if isinstance(scene, str) and scene.strip():
        return scene.strip()
    return cfg.sign_scene


def _resolve_personal_product_code(cfg: AlipayEnvConfig, listing: MarketListing) -> str:
    """Resolve personal product code."""
    extra = listing.extra_json or {}
    code = extra.get("personal_product_code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    return cfg.personal_product_code


def _period_type_for_interval(interval: str) -> str:
    """Period type for interval."""
    if interval == "year":
        return "YEAR"
    return "MONTH"


def build_agreement_sign_form_html(
    *,
    cfg: AlipayEnvConfig,
    subscription: MarketSubscription,
    listing: MarketListing,
    external_logon_id: str,
    notify_url: str,
    return_url: Optional[str],
) -> str:
    """Return auto-submit HTML form for ``alipay.user.agreement.page.sign``."""
    if not subscription.external_agreement_no:
        raise ValueError("subscription.external_agreement_no is required")

    client = build_alipay_client(cfg)
    interval = listing_billing_interval(listing.extra_json)
    period_rule = PeriodRuleParams()
    period_rule.period_type = _period_type_for_interval(interval)
    period_rule.period = 1
    period_rule.execute_time = listing_execute_time(listing.extra_json)
    period_rule.single_amount = minor_to_yuan_str(listing.price_minor)

    model = AlipayUserAgreementPageSignModel()
    model.product_code = "GENERAL_WITHHOLDING"
    model.personal_product_code = _resolve_personal_product_code(cfg, listing)
    model.sign_scene = _resolve_sign_scene(cfg, listing)
    model.external_agreement_no = subscription.external_agreement_no
    model.external_logon_id = external_logon_id[:100]
    model.sign_validity_period = "2m"
    model.period_rule_params = period_rule

    request = AlipayUserAgreementPageSignRequest(biz_model=model)
    request.notify_url = notify_url
    if return_url:
        request.return_url = return_url

    return client.page_execute(request, http_method="POST")


def listing_sign_metadata(listing: MarketListing) -> dict[str, Any]:
    """Listing sign metadata."""
    interval = listing_billing_interval(listing.extra_json)
    return {
        "interval": interval,
        "execute_time": listing_execute_time(listing.extra_json),
        "price_minor": listing.price_minor,
        "currency": listing.currency,
    }
