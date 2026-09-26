"""Online-library uploads need vod2 and one-label COS hosts in connect-src."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.features.vod.browser_csp import vod_browser_connect_sources
from services.infrastructure.http import middleware as middleware_module

INDEX_HTML = Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def test_vod_connect_sources_cover_upload_api_and_parks() -> None:
    """SDK control plane and the parks PrepareUploadUGC returned are listed."""
    sources = vod_browser_connect_sources()
    assert "https://vod2.qcloud.com" in sources.split()
    assert "https://vod2.dnsv1.com" in sources.split()
    assert "https://*.cos.ap-shanghai.myqcloud.com" in sources.split()
    assert "https://*.cos.ap-chongqing.myqcloud.com" in sources.split()
    assert "https://*.myqcloud.com" not in sources.split()


def test_vite_index_csp_lists_vod_upload_hosts() -> None:
    """Dev meta CSP must match the server allowlist (Vite does not use the header)."""
    content = INDEX_HTML.read_text(encoding="utf-8")
    for origin in vod_browser_connect_sources().split():
        assert origin in content


@pytest.mark.asyncio
async def test_production_csp_allows_vod_upload_when_feature_on() -> None:
    """FEATURE_VOD adds upload hosts to connect-src and leaves media-src alone."""
    request = MagicMock()
    request.url.scheme = "https"
    request.url.path = "/admin"
    request.state = SimpleNamespace(csp_nonce="testnonce123")
    response = MagicMock()
    response.headers = {}

    async def _call_next(_req):
        return response

    with patch.object(middleware_module, "is_https", return_value=False):
        with patch.object(middleware_module, "config") as mock_config:
            mock_config.debug = False
            mock_config.FEATURE_VOD = True
            with patch.object(middleware_module, "cos_showcase_enabled", return_value=False):
                with patch.object(middleware_module, "cos_training_enabled", return_value=False):
                    with patch.object(
                        middleware_module,
                        "cos_auth_login_csp_enabled",
                        return_value=False,
                    ):
                        with patch("services.auth.tsec.csp.tsec_csp_enabled", return_value=False):
                            result = await middleware_module.add_security_headers(request, _call_next)

    csp = result.headers["Content-Security-Policy"]
    assert "https://vod2.qcloud.com" in csp
    assert "https://*.cos.ap-shanghai.myqcloud.com" in csp
    assert "media-src 'self' blob:;" in csp


@pytest.mark.asyncio
async def test_production_csp_omits_vod_hosts_when_feature_off() -> None:
    """A MagicMock config flag must not widen connect-src."""
    request = MagicMock()
    request.url.scheme = "https"
    request.url.path = "/admin"
    request.state = SimpleNamespace(csp_nonce="testnonce123")
    response = MagicMock()
    response.headers = {}

    async def _call_next(_req):
        return response

    with patch.object(middleware_module, "is_https", return_value=False):
        with patch.object(middleware_module, "config") as mock_config:
            mock_config.debug = False
            with patch.object(middleware_module, "cos_showcase_enabled", return_value=False):
                with patch.object(middleware_module, "cos_training_enabled", return_value=False):
                    with patch.object(
                        middleware_module,
                        "cos_auth_login_csp_enabled",
                        return_value=False,
                    ):
                        with patch("services.auth.tsec.csp.tsec_csp_enabled", return_value=False):
                            result = await middleware_module.add_security_headers(request, _call_next)

    csp = result.headers["Content-Security-Policy"]
    assert "vod2.qcloud.com" not in csp
    assert "myqcloud.com" not in csp
