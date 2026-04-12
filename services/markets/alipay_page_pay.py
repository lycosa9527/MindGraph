"""Build Alipay PC page-pay HTML form via official SDK (gateway)."""

import logging
from typing import Optional

from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest

from services.markets.alipay_settings import AlipayEnvConfig

logger = logging.getLogger(__name__)


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
    client_config = AlipayClientConfig(sandbox_debug=cfg.sandbox)
    client_config.server_url = cfg.server_url
    client_config.app_id = cfg.app_id
    client_config.app_private_key = cfg.app_private_key
    client_config.alipay_public_key = cfg.alipay_public_key
    client_config.sign_type = "RSA2"
    client = DefaultAlipayClient(client_config, logger=logger)

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
