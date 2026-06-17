"""
Build Alipay PC page-pay HTML form via official SDK (gateway).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional

from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest

from services.markets.alipay_client import build_alipay_client
from services.markets.alipay_settings import AlipayEnvConfig


def build_page_pay_form_html(
    *,
    cfg: AlipayEnvConfig,
    out_trade_no: str,
    total_amount_yuan: str,
    subject: str,
    notify_url: str,
    return_url: Optional[str],
) -> str:
    """Return auto-submit HTML form that POSTs to Alipay gateway."""
    client = build_alipay_client(cfg)

    model = AlipayTradePagePayModel()
    model.out_trade_no = out_trade_no
    model.total_amount = total_amount_yuan
    model.subject = subject
    model.product_code = "FAST_INSTANT_TRADE_PAY"

    request = AlipayTradePagePayRequest(biz_model=model)
    request.notify_url = notify_url
    if return_url:
        request.return_url = return_url

    return client.page_execute(request, http_method="POST")
