"""WeChat / DingTalk QR widget CSP hosts match the official embed surface."""

from __future__ import annotations

from pathlib import Path

from services.auth.oauth.oauth_csp import (
    DINGTALK_CSP_CONNECT_SRC,
    DINGTALK_CSP_FRAME_SRC,
    DINGTALK_CSP_SCRIPT_SRC,
    OAUTH_QR_CSP_CONNECT_SRC,
    OAUTH_QR_CSP_FRAME_SRC,
    OAUTH_QR_CSP_SCRIPT_SRC,
    WECHAT_CSP_CONNECT_SRC,
    WECHAT_CSP_EXCLUDED_HOSTS,
    WECHAT_CSP_FRAME_SRC,
    WECHAT_CSP_SCRIPT_SRC,
)
from services.infrastructure.http.security_csp import production_content_security_policy


def test_wechat_csp_hosts_match_official_wxlogin_embed() -> None:
    """Parent CSP lists every 网站应用 host WxLogin.js and qrconnect use."""
    assert WECHAT_CSP_SCRIPT_SRC == "https://res.wx.qq.com"
    assert WECHAT_CSP_FRAME_SRC == "https://open.weixin.qq.com"
    assert "https://open.weixin.qq.com" in WECHAT_CSP_CONNECT_SRC
    assert "https://long.open.weixin.qq.com" in WECHAT_CSP_CONNECT_SRC


def test_wechat_csp_excludes_other_wechat_products() -> None:
    """企业微信 / 公众号 / 网页微信 hosts are not part of 网站应用 login."""
    allow = " ".join((WECHAT_CSP_SCRIPT_SRC, WECHAT_CSP_FRAME_SRC, WECHAT_CSP_CONNECT_SRC))
    for host in WECHAT_CSP_EXCLUDED_HOSTS:
        assert host not in allow


def test_production_csp_includes_full_wechat_qr_allowlist() -> None:
    """Production header carries script, frame, and connect WeChat hosts."""
    csp = production_content_security_policy(None, "'none'", "", "media-src 'self' blob:; ")
    assert WECHAT_CSP_SCRIPT_SRC in csp
    assert WECHAT_CSP_FRAME_SRC in csp
    for host in WECHAT_CSP_CONNECT_SRC.split():
        assert host in csp
    assert DINGTALK_CSP_SCRIPT_SRC in csp
    assert DINGTALK_CSP_FRAME_SRC in csp
    assert DINGTALK_CSP_CONNECT_SRC in csp
    for host in WECHAT_CSP_EXCLUDED_HOSTS:
        assert host not in csp


def test_vite_index_csp_includes_wechat_qr_hosts() -> None:
    """Vite meta CSP must match the official WeChat widget hosts."""
    index_html = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
    content = index_html.read_text(encoding="utf-8")
    for host in (
        *OAUTH_QR_CSP_SCRIPT_SRC.split(),
        *OAUTH_QR_CSP_FRAME_SRC.split(),
        *OAUTH_QR_CSP_CONNECT_SRC.split(),
    ):
        assert host in content
    for host in WECHAT_CSP_EXCLUDED_HOSTS:
        assert host not in content
