"""Tencent T-Sec captcha (separate from the SVG captcha modules)."""

from services.auth.tsec.aid_encrypted import mint_aid_encrypted
from services.auth.tsec.config import (
    PROVIDER_LEGACY,
    PROVIDER_TSEC,
    effective_captcha_provider,
    public_captcha_app_id,
    requested_captcha_provider,
    tsec_credentials_ready,
)
from services.auth.tsec.csp import tsec_csp_enabled
from services.auth.tsec.exchange import exchange_tsec_ticket
from services.auth.tsec.verify import verify_tsec_ticket

__all__ = [
    "PROVIDER_LEGACY",
    "PROVIDER_TSEC",
    "effective_captcha_provider",
    "exchange_tsec_ticket",
    "mint_aid_encrypted",
    "public_captcha_app_id",
    "requested_captcha_provider",
    "tsec_credentials_ready",
    "tsec_csp_enabled",
    "verify_tsec_ticket",
]
