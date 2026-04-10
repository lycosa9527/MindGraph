"""Tests for email_login_cn_api_geo (API-layer CN email policy)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from services.auth import email_login_cn_api_geo as mod


async def test_email_login_cn_api_blocks_cn_when_email_user() -> None:
    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    req.headers = {}
    req.cookies = {}

    user = MagicMock()
    user.id = 1
    user.email = "a@b.com"
    user.email_login_whitelisted_from_cn = False

    with patch.object(mod, "EMAIL_LOGIN_CN_BLOCK_ENABLED", True):
        with patch.object(mod, "AUTH_MODE", "standard"):
            with patch.object(mod, "_resolve_user_for_email_cn_geo", new_callable=AsyncMock, return_value=user):
                with patch.object(
                    mod,
                    "email_cn_geo_blocked",
                    return_value=(True, "email_login_blocked_in_mainland_china", True),
                ):
                    with patch.object(mod, "json_forbidden_cn_geo") as jfg:
                        jfg.return_value = MagicMock(status_code=403)
                        out = await mod.maybe_enforce_email_login_cn_geo_api_async(req)

    assert out is not None
    jfg.assert_called_once()


async def test_email_login_cn_api_skips_phone_only_user() -> None:
    req = MagicMock()
    req.url.path = "/api/auth/api-token"
    user = MagicMock()
    user.email = None

    with patch.object(mod, "EMAIL_LOGIN_CN_BLOCK_ENABLED", True):
        with patch.object(mod, "AUTH_MODE", "standard"):
            with patch.object(mod, "_resolve_user_for_email_cn_geo", new_callable=AsyncMock, return_value=user):
                out = await mod.maybe_enforce_email_login_cn_geo_api_async(req)

    assert out is None
