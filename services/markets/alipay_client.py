"""Create configured Alipay Open Platform client."""

import logging

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient

from services.markets.alipay_settings import AlipayEnvConfig

logger = logging.getLogger(__name__)


def build_alipay_client(cfg: AlipayEnvConfig) -> DefaultAlipayClient:
    """Build alipay client."""
    client_config = AlipayClientConfig(sandbox_debug=cfg.sandbox)
    client_config.server_url = cfg.server_url
    client_config.app_id = cfg.app_id
    client_config.app_private_key = cfg.app_private_key
    client_config.alipay_public_key = cfg.alipay_public_key
    client_config.sign_type = "RSA2"
    return DefaultAlipayClient(client_config, logger=logger)
