"""
Alipay gateway configuration from environment.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from services.markets.alipay_certs import (
    AlipayCertMaterial,
    cert_bundle_present,
    load_cert_material_from_dir,
)

DEFAULT_ALIPAY_CERT_DIR = "data/alipay-certs"

logger = logging.getLogger(__name__)

ALIPAY_GATEWAY_PRODUCTION = "https://openapi.alipay.com/gateway.do"
ALIPAY_GATEWAY_SANDBOX = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"


@dataclass(frozen=True)
class AlipayEnvConfig:
    """Alipay Open Platform settings for 电脑网站支付.

    Product docs live under OpenAPI v3 (``alipay.trade.page.pay``). Official
    Python support is the 通用版 SDK: ``page_execute`` posts a signed HTML
    form to ``gateway.do`` (method version ``1.0``). Certificate-mode apps
    also send ``app_cert_sn`` and ``alipay_root_cert_sn``.
    """

    app_id: str
    app_private_key: str
    alipay_public_key: str
    sandbox: bool
    notify_base_url: str
    sign_scene: str
    personal_product_code: str
    app_cert_sn: str = ""
    alipay_root_cert_sn: str = ""

    @property
    def server_url(self) -> str:
        """Alipay gateway URL (production or current sandbox host)."""
        if self.sandbox:
            return ALIPAY_GATEWAY_SANDBOX
        return ALIPAY_GATEWAY_PRODUCTION

    @property
    def uses_certificate_mode(self) -> bool:
        """True when the open-platform app is 证书模式."""
        return bool(self.app_cert_sn and self.alipay_root_cert_sn)


def resolve_alipay_cert_dir() -> Path:
    """Cert upload folder; defaults to ``data/alipay-certs`` on the server."""
    raw = os.getenv("ALIPAY_CERT_DIR", DEFAULT_ALIPAY_CERT_DIR).strip()
    if not raw:
        return Path(DEFAULT_ALIPAY_CERT_DIR)
    return Path(raw)


def _load_cert_dir_material(app_id: str) -> AlipayCertMaterial | None:
    cert_dir = resolve_alipay_cert_dir()
    if not cert_bundle_present(cert_dir, app_id):
        return None
    try:
        return load_cert_material_from_dir(cert_dir, app_id)
    except (OSError, ValueError) as exc:
        logger.error("[Markets] Failed to load ALIPAY_CERT_DIR: %s", exc)
        return None


def load_alipay_config() -> AlipayEnvConfig | None:
    """Return config when Alipay credentials are present; otherwise None."""
    app_id = os.getenv("ALIPAY_APP_ID", "").strip()
    if not app_id:
        return None
    cert_material = _load_cert_dir_material(app_id)
    app_private_key = (
        cert_material.app_private_key_pkcs1 if cert_material else os.getenv("ALIPAY_APP_PRIVATE_KEY", "").strip()
    )
    alipay_public_key = (
        cert_material.alipay_public_key if cert_material else os.getenv("ALIPAY_ALIPAY_PUBLIC_KEY", "").strip()
    )
    if not app_private_key or not alipay_public_key:
        return None
    sandbox = os.getenv("ALIPAY_SANDBOX", "false").lower() == "true"
    notify_base = os.getenv("ALIPAY_NOTIFY_BASE_URL", "").strip().rstrip("/")
    sign_scene = os.getenv("ALIPAY_SIGN_SCENE", "INDUSTRY|DIGITAL_MEDIA").strip()
    personal_product_code = os.getenv("ALIPAY_PERSONAL_PRODUCT_CODE", "CYCLE_PAY_AUTH_P").strip()
    return AlipayEnvConfig(
        app_id=app_id,
        app_private_key=app_private_key,
        alipay_public_key=alipay_public_key,
        sandbox=sandbox,
        notify_base_url=notify_base,
        sign_scene=sign_scene,
        personal_product_code=personal_product_code,
        app_cert_sn=cert_material.app_cert_sn if cert_material else "",
        alipay_root_cert_sn=cert_material.alipay_root_cert_sn if cert_material else "",
    )
