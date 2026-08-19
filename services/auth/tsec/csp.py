"""CSP host-sources required by Tencent Captcha 2.0 (TJCaptcha.js)."""

from __future__ import annotations

from services.auth.tsec.config import PROVIDER_TSEC, effective_captcha_provider

TSEC_CSP_SCRIPT_SRC = "https://turing.captcha.qcloud.com"
# TJCaptcha injects <link> stylesheets (and @font-face) from both CDNs. Blocking
# either host leaves the widget blank and surfaces captcha_show_timeout.
TSEC_CSP_STYLE_SRC = "https://turing.captcha.qcloud.com https://turing.captcha.gtimg.com"
TSEC_CSP_FONT_SRC = TSEC_CSP_STYLE_SRC
TSEC_CSP_FRAME_SRC = (
    "https://turing.captcha.qcloud.com https://turing.captcha.gtimg.com "
    "https://ssl.captcha.qq.com https://captcha.gtimg.com"
)
TSEC_CSP_CONNECT_SRC = TSEC_CSP_FRAME_SRC


def tsec_csp_enabled() -> bool:
    """True when the live captcha provider needs Tencent Captcha 2.0 hosts."""
    return effective_captcha_provider() == PROVIDER_TSEC


def tsec_csp_extra(hosts: str) -> str:
    """Leading-space host list when T-Sec is live, else empty."""
    return f" {hosts}" if tsec_csp_enabled() else ""
