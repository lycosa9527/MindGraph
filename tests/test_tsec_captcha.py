"""Tencent T-Sec captcha provider: env gate, verify, exchange, CSP."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.auth.tsec import TsecExchangeRequest, exchange_tsec_captcha
from services.auth.tsec import config as tsec_config
from services.auth.tsec.client import TsecCaptchaClientError
from services.auth.tsec.csp import (
    TSEC_CSP_HOSTS,
    TSEC_CSP_SCRIPT_SRC,
    TSEC_CSP_STYLE_SRC,
    tsec_csp_enabled,
)
from services.auth.tsec.errors import CAPTCHA_CODE_REASONS, reason_for_client_error
from services.auth.tsec.verify import verify_tsec_ticket
from services.infrastructure.http import middleware as middleware_module
from services.infrastructure.security import production_secrets_guard as guard_module


def _tsec_ready_env() -> dict[str, str]:
    return {
        "CAPTCHA_PROVIDER": "tsec",
        "TENCENT_CAPTCHA_APP_ID": "199999164",
        "TENCENT_CAPTCHA_APP_SECRET_KEY": "test-app-secret",
        "TENCENT_CAPTCHA_SECRET_ID": "AKIDtest",
        "TENCENT_CAPTCHA_SECRET_KEY": "test-cam-secret",
    }


def test_effective_provider_falls_back_to_legacy_without_credentials(monkeypatch) -> None:
    """Default tsec without console keys must not break local login."""
    monkeypatch.setenv("CAPTCHA_PROVIDER", "tsec")
    monkeypatch.delenv("TENCENT_CAPTCHA_APP_ID", raising=False)
    monkeypatch.delenv("TENCENT_CAPTCHA_APP_SECRET_KEY", raising=False)
    monkeypatch.delenv("TENCENT_CAPTCHA_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENT_CAPTCHA_SECRET_KEY", raising=False)
    monkeypatch.delenv("TENCENT_SMS_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENT_SMS_SECRET_KEY", raising=False)
    assert tsec_config.effective_captcha_provider() == tsec_config.PROVIDER_LEGACY
    assert tsec_config.public_captcha_app_id() == ""
    assert tsec_csp_enabled() is False


def test_effective_provider_tsec_when_credentials_ready(monkeypatch) -> None:
    """T-Sec is live only when AppId, AppSecretKey, and CAM keys are set."""
    for key, value in _tsec_ready_env().items():
        monkeypatch.setenv(key, value)
    assert tsec_config.effective_captcha_provider() == tsec_config.PROVIDER_TSEC
    assert tsec_config.public_captcha_app_id() == "199999164"
    assert tsec_csp_enabled() is True


def test_legacy_alias_forces_svg_provider(monkeypatch) -> None:
    """CAPTCHA_PROVIDER=legacy keeps the SVG captcha even if T-Sec keys exist."""
    for key, value in _tsec_ready_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("CAPTCHA_PROVIDER", "legacy")
    assert tsec_config.effective_captcha_provider() == tsec_config.PROVIDER_LEGACY


@pytest.mark.asyncio
async def test_verify_rejects_disaster_ticket_without_api_call() -> None:
    """trerror_ tickets are fail-closed and never sent to Tencent."""
    with patch("services.auth.tsec.verify.describe_captcha_result", new_callable=AsyncMock) as mock_api:
        ok, reason = await verify_tsec_ticket("trerror_1001_199999164_1", "@abc", "1.1.1.1")
    assert ok is False
    assert reason == "disaster_ticket"
    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_verify_accepts_captcha_code_one() -> None:
    """DescribeCaptchaResult CaptchaCode=1 is the only pass."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        new_callable=AsyncMock,
        return_value={"CaptchaCode": 1, "CaptchaMsg": "OK", "EvilLevel": 0},
    ):
        ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is True
    assert reason is None


@pytest.mark.parametrize("code", [7, 8, 9, 15, 16, 21, 26, 100])
@pytest.mark.asyncio
async def test_verify_rejects_non_success_codes(code: int) -> None:
    """Non-1 CaptchaCode values are denied with official reason names."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        new_callable=AsyncMock,
        return_value={"CaptchaCode": code, "CaptchaMsg": "fail"},
    ):
        ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is False
    assert reason == CAPTCHA_CODE_REASONS[code]


@pytest.mark.asyncio
async def test_verify_maps_unknown_captcha_code() -> None:
    """Undocumented CaptchaCode values stay fail-closed with a numeric reason."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        new_callable=AsyncMock,
        return_value={"CaptchaCode": 0, "CaptchaMsg": "not valid"},
    ):
        ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is False
    assert reason == "captcha_code_0"


@pytest.mark.parametrize(
    ("api_code", "expected"),
    [
        ("UnauthorizedOperation.Unauthorized", "cloud_api_unauthorized"),
        ("UnauthorizedOperation.ErrAuth", "cloud_api_auth"),
        ("InternalError", "cloud_api_internal"),
        ("MissingParameter", "cloud_api_missing_parameter"),
        ("AuthFailure.SignatureFailure", "cloud_api_AuthFailure.SignatureFailure"),
    ],
)
def test_reason_for_cloud_api_error(api_code: str, expected: str) -> None:
    """36926/36927 Cloud API Error.Code values have stable fail-closed reasons."""
    assert reason_for_client_error(api_code) == expected


@pytest.mark.asyncio
async def test_verify_maps_cloud_api_unauthorized() -> None:
    """Unpaid / no-package Cloud API errors do not skip captcha."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        new_callable=AsyncMock,
        side_effect=TsecCaptchaClientError("UnauthorizedOperation.Unauthorized"),
    ):
        ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is False
    assert reason == "cloud_api_unauthorized"


@pytest.mark.asyncio
async def test_verify_rejects_evil_level_100() -> None:
    """Invisible-mode malicious score is denied even when CaptchaCode is 1."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        new_callable=AsyncMock,
        return_value={"CaptchaCode": 1, "CaptchaMsg": "OK", "EvilLevel": 100},
    ):
        ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is False
    assert reason == "evil_level"


@pytest.mark.asyncio
async def test_verify_fails_closed_on_provider_timeout() -> None:
    """Cloud API timeout does not skip captcha."""
    with patch(
        "services.auth.tsec.verify.describe_captcha_result",
        new_callable=AsyncMock,
        side_effect=TsecCaptchaClientError("timeout"),
    ):
        ok, reason = await verify_tsec_ticket("tr03validticket", "@Vki", "1.1.1.1")
    assert ok is False
    assert reason == "provider_error"


@pytest.mark.asyncio
async def test_exchange_404_when_provider_is_legacy(monkeypatch) -> None:
    """Exchange is not available unless T-Sec is the effective provider."""
    monkeypatch.setenv("CAPTCHA_PROVIDER", "legacy")
    request = MagicMock()
    request.cookies = {}
    request.headers = {}
    with pytest.raises(HTTPException) as exc_info:
        await exchange_tsec_captcha(
            TsecExchangeRequest(ticket="tr03validticket", randstr="@Vki"),
            request,
            MagicMock(),
            None,
        )
    assert exc_info.value.status_code == 404


def test_production_guard_requires_tsec_secrets() -> None:
    """Non-debug tsec without keys must refuse to start."""
    with patch.object(guard_module, "_require_non_debug", return_value=True):
        with patch.object(guard_module, "_guard_database_url", return_value=None):
            with patch.object(guard_module, "_guard_redis_url", return_value=None):
                with patch.object(guard_module, "AUTH_MODE", "standard"):
                    with patch.dict(
                        "os.environ",
                        {
                            "CAPTCHA_PROVIDER": "tsec",
                            "TENCENT_CAPTCHA_APP_ID": "",
                            "TENCENT_CAPTCHA_APP_SECRET_KEY": "",
                            "TENCENT_CAPTCHA_SECRET_ID": "",
                            "TENCENT_CAPTCHA_SECRET_KEY": "",
                            "TENCENT_SMS_SECRET_ID": "",
                            "TENCENT_SMS_SECRET_KEY": "",
                            "FEATURE_OAUTH_LOGIN": "False",
                            "FEATURE_GEWE": "False",
                            "FEATURE_SMART_RESPONSE": "False",
                        },
                        clear=False,
                    ):
                        with pytest.raises(RuntimeError, match="CAPTCHA_PROVIDER=tsec"):
                            guard_module.enforce_production_security_guards()


@pytest.mark.asyncio
async def test_production_csp_includes_tsec_hosts_when_enabled() -> None:
    """T-Sec CSP hosts appear only when the live provider is tsec."""
    request = MagicMock()
    request.url.scheme = "https"
    request.state = SimpleNamespace(csp_nonce="testnonce123")
    response = MagicMock()
    response.headers = {}

    async def _call_next(_req):
        return response

    with patch.object(middleware_module, "is_https", return_value=False):
        with patch.object(middleware_module, "config") as mock_config:
            mock_config.debug = False
            with patch.object(middleware_module, "cos_showcase_enabled", return_value=False):
                with patch("services.auth.tsec.csp.tsec_csp_enabled", return_value=True):
                    result = await middleware_module.add_security_headers(request, _call_next)

    csp = result.headers["Content-Security-Policy"]
    assert TSEC_CSP_SCRIPT_SRC in csp
    assert "https://ssl.captcha.qq.com" in csp
    assert "https://turing.captcha.gtimg.com" in csp
    assert f"script-src 'self' 'nonce-testnonce123' {TSEC_CSP_SCRIPT_SRC}" in csp
    assert f"style-src 'self' 'unsafe-inline' {TSEC_CSP_STYLE_SRC}" in csp
    assert f"font-src 'self' data: {TSEC_CSP_STYLE_SRC}" in csp
    assert "worker-src 'self' blob:" in csp


def test_vite_index_csp_allows_tsec_stylesheets() -> None:
    """Vite document CSP must list TJCaptcha CSS hosts (dev uses the meta tag)."""
    index_html = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
    content = index_html.read_text(encoding="utf-8")
    assert TSEC_CSP_HOSTS in content
    assert "script-src 'self' 'unsafe-inline'" in content
    assert "worker-src 'self' blob:" in content
