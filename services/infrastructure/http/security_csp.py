"""Content-Security-Policy strings for SPA, debug, and Word add-in responses."""

from __future__ import annotations

from services.auth.oauth.oauth_csp import (
    OAUTH_QR_CSP_CONNECT_SRC,
    OAUTH_QR_CSP_FRAME_SRC,
    OAUTH_QR_CSP_SCRIPT_SRC,
    oauth_qr_csp_extra,
)
from services.auth.tsec.csp import (
    TSEC_CSP_CONNECT_SRC,
    TSEC_CSP_FONT_SRC,
    TSEC_CSP_FRAME_SRC,
    TSEC_CSP_SCRIPT_SRC,
    TSEC_CSP_STYLE_SRC,
    TSEC_CSP_WORKER_SRC,
    tsec_csp_extra,
)

OFFICE_JS_CDN = "https://appsforoffice.microsoft.com"
WORD_ADDIN_MANUAL_FRAME = "https://365.kdocs.cn"


def word_addin_content_security_policy() -> str:
    """
    CSP for ``/word-addin/*`` Office.js shell pages.

    Task panes load Office.js from Microsoft's CDN and use inline boot scripts;
    the main SPA CSP (nonce / no external scripts) would break the add-in.
    Manual task pane embeds the platform quick guide (Kingsoft Docs).

    ``frame-ancestors`` stays permissive enough for Office desktop/web hosts;
    pairing with ``X-Frame-Options: DENY`` would block the task pane runtime.
    """
    return (
        "default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' {OFFICE_JS_CDN}"
        f"{tsec_csp_extra(TSEC_CSP_SCRIPT_SRC)}{oauth_qr_csp_extra(OAUTH_QR_CSP_SCRIPT_SRC)}; "
        "worker-src 'self' blob:; "
        f"style-src 'self' 'unsafe-inline'{tsec_csp_extra(TSEC_CSP_STYLE_SRC)}; "
        "img-src 'self' data: https: blob:; "
        f"font-src 'self' data:{tsec_csp_extra(TSEC_CSP_FONT_SRC)}; "
        f"connect-src 'self' {OFFICE_JS_CDN}"
        f"{tsec_csp_extra(TSEC_CSP_CONNECT_SRC)}{oauth_qr_csp_extra(OAUTH_QR_CSP_CONNECT_SRC)}; "
        "media-src 'self' blob:; "
        f"frame-src 'self' blob: {WORD_ADDIN_MANUAL_FRAME}"
        f"{tsec_csp_extra(TSEC_CSP_FRAME_SRC)}{oauth_qr_csp_extra(OAUTH_QR_CSP_FRAME_SRC)}; "
        "frame-ancestors *; "
        "base-uri 'self'; "
        "form-action 'self';"
    )


def debug_content_security_policy(
    frame_ancestors: str,
    cos_connect_clause: str,
    media_src: str,
) -> str:
    """Permissive CSP for DEBUG (Swagger CDN + OAuth QR + optional T-Sec)."""
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        f"https://cdn.jsdelivr.net{tsec_csp_extra(TSEC_CSP_SCRIPT_SRC)}"
        f"{oauth_qr_csp_extra(OAUTH_QR_CSP_SCRIPT_SRC)}; "
        "worker-src 'self' blob:; "
        f"style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net{tsec_csp_extra(TSEC_CSP_STYLE_SRC)}; "
        "img-src 'self' data: http: https: blob: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
        f"font-src 'self' data: https://cdn.jsdelivr.net{tsec_csp_extra(TSEC_CSP_FONT_SRC)}; "
        "connect-src 'self' ws: wss: blob: https://cdn.jsdelivr.net"
        f"{cos_connect_clause}{tsec_csp_extra(TSEC_CSP_CONNECT_SRC)}"
        f"{oauth_qr_csp_extra(OAUTH_QR_CSP_CONNECT_SRC)}; "
        f"{media_src}"
        "frame-src 'self' blob: https://view.officeapps.live.com"
        f"{tsec_csp_extra(TSEC_CSP_FRAME_SRC)}{oauth_qr_csp_extra(OAUTH_QR_CSP_FRAME_SRC)}; "
        f"frame-ancestors {frame_ancestors}; "
        "base-uri 'self'; "
        "form-action 'self';"
    )


def production_content_security_policy(
    csp_nonce: str | None,
    frame_ancestors: str,
    cos_connect_clause: str,
    media_src: str,
) -> str:
    """
    Production CSP. SPA shells set ``csp_nonce`` so script-src drops
    ``'unsafe-inline'``. Official WeChat / DingTalk QR widget hosts are
    always listed (see ``oauth_csp``).
    """
    nonce_part = f"'nonce-{csp_nonce}'" if csp_nonce else "'unsafe-inline'"
    script_src = (
        f"script-src 'self' {nonce_part}"
        f"{tsec_csp_extra(TSEC_CSP_SCRIPT_SRC)}"
        f"{oauth_qr_csp_extra(OAUTH_QR_CSP_SCRIPT_SRC)}; "
    )
    return (
        "default-src 'self'; "
        f"{script_src}"
        f"worker-src 'self'{tsec_csp_extra(TSEC_CSP_WORKER_SRC)}; "
        f"style-src 'self' 'unsafe-inline'{tsec_csp_extra(TSEC_CSP_STYLE_SRC)}; "
        "img-src 'self' data: http: https: blob:; "
        f"font-src 'self' data:{tsec_csp_extra(TSEC_CSP_FONT_SRC)}; "
        f"connect-src 'self' ws: wss: blob:{cos_connect_clause}"
        f"{tsec_csp_extra(TSEC_CSP_CONNECT_SRC)}"
        f"{oauth_qr_csp_extra(OAUTH_QR_CSP_CONNECT_SRC)}; "
        f"{media_src}"
        "frame-src 'self' blob: https://view.officeapps.live.com"
        f"{tsec_csp_extra(TSEC_CSP_FRAME_SRC)}{oauth_qr_csp_extra(OAUTH_QR_CSP_FRAME_SRC)}; "
        f"frame-ancestors {frame_ancestors}; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
