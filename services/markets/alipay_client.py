"""
Create configured Alipay Open Platform client.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient

from services.markets.alipay_settings import AlipayEnvConfig

logger = logging.getLogger(__name__)


def build_alipay_client(cfg: AlipayEnvConfig) -> DefaultAlipayClient:
    """Build the official Python 通用版 client (RSA2, gateway.do)."""
    client_config = AlipayClientConfig(sandbox_debug=False)
    client_config.server_url = cfg.server_url
    client_config.app_id = cfg.app_id
    client_config.app_private_key = cfg.app_private_key
    client_config.alipay_public_key = cfg.alipay_public_key
    client_config.sign_type = "RSA2"
    return DefaultAlipayClient(client_config, logger=logger)


def apply_cert_sns(request: Any, cfg: AlipayEnvConfig) -> None:
    """Attach certificate-mode serials when the open-platform app requires them."""
    if cfg.app_cert_sn:
        request.add_other_text_param("app_cert_sn", cfg.app_cert_sn)
    if cfg.alipay_root_cert_sn:
        request.add_other_text_param("alipay_root_cert_sn", cfg.alipay_root_cert_sn)
