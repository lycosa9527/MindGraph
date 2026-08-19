"""CSP host-sources required by Tencent Captcha 2.0 (TJCaptcha.js)."""

from __future__ import annotations

from services.auth.tsec.config import PROVIDER_TSEC, effective_captcha_provider

# One host list for every fetch type TJCaptcha uses (script, style, font,
# connect, frame). qcloud is the 2.0 entry; gtimg is the runtime fallback;
# ssl.captcha.qq.com / captcha.gtimg.com are iframe/XHR peers.
# Same-origin blob: workers are required in production (worker-src).
TSEC_CSP_HOSTS = (
    "https://turing.captcha.qcloud.com "
    "https://turing.captcha.gtimg.com "
    "https://ssl.captcha.qq.com "
    "https://captcha.gtimg.com"
)
TSEC_CSP_SCRIPT_SRC = TSEC_CSP_HOSTS
TSEC_CSP_STYLE_SRC = TSEC_CSP_HOSTS
TSEC_CSP_FONT_SRC = TSEC_CSP_HOSTS
TSEC_CSP_FRAME_SRC = TSEC_CSP_HOSTS
TSEC_CSP_CONNECT_SRC = TSEC_CSP_HOSTS
TSEC_CSP_WORKER_SRC = "blob:"


def tsec_csp_enabled() -> bool:
    """True when the live captcha provider needs Tencent Captcha 2.0 hosts."""
    return effective_captcha_provider() == PROVIDER_TSEC


def tsec_csp_extra(hosts: str) -> str:
    """Leading-space host list when T-Sec is live, else empty."""
    return f" {hosts}" if tsec_csp_enabled() else ""
