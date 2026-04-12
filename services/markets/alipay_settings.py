"""Alipay gateway configuration from environment."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AlipayEnvConfig:
    """Alipay Open Platform (gateway) settings.

    The official Python SDK uses the unified gateway (``gateway.do``) with API
    methods such as ``alipay.trade.page.pay`` — same business contract as Open
    Docs for PC page pay.
    """

    app_id: str
    app_private_key: str
    alipay_public_key: str
    sandbox: bool
    notify_base_url: str

    @property
    def server_url(self) -> str:
        if self.sandbox:
            return "https://openapi.alipaydev.com/gateway.do"
        return "https://openapi.alipay.com/gateway.do"


def load_alipay_config() -> AlipayEnvConfig | None:
    """Return config when Alipay credentials are present; otherwise None."""
    app_id = os.getenv("ALIPAY_APP_ID", "").strip()
    app_private_key = os.getenv("ALIPAY_APP_PRIVATE_KEY", "").strip()
    alipay_public_key = os.getenv("ALIPAY_ALIPAY_PUBLIC_KEY", "").strip()
    if not app_id or not app_private_key or not alipay_public_key:
        return None
    sandbox = os.getenv("ALIPAY_SANDBOX", "false").lower() == "true"
    notify_base = os.getenv("ALIPAY_NOTIFY_BASE_URL", "").strip().rstrip("/")
    return AlipayEnvConfig(
        app_id=app_id,
        app_private_key=app_private_key,
        alipay_public_key=alipay_public_key,
        sandbox=sandbox,
        notify_base_url=notify_base,
    )
