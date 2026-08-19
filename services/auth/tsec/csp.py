"""CSP host-sources required by Tencent Captcha 2.0 (TJCaptcha.js)."""

from __future__ import annotations

from services.auth.tsec.config import PROVIDER_TSEC, effective_captcha_provider

TSEC_CSP_SCRIPT_SRC = "https://turing.captcha.qcloud.com"
TSEC_CSP_FRAME_SRC = "https://turing.captcha.qcloud.com https://ssl.captcha.qq.com https://captcha.gtimg.com"
TSEC_CSP_CONNECT_SRC = "https://turing.captcha.qcloud.com https://ssl.captcha.qq.com https://captcha.gtimg.com"


def tsec_csp_enabled() -> bool:
    """True when the live captcha provider needs Tencent Captcha 2.0 hosts."""
    return effective_captcha_provider() == PROVIDER_TSEC
