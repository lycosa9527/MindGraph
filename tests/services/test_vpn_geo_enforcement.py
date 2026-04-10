"""Tests for VPN / CN geo enforcement helpers and middleware hook."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR

from services.auth import vpn_geo_enforcement as vge


def test_should_kick_vpn_transition() -> None:
    assert vge.should_kick_vpn_transition("US", "CN") is True
    assert vge.should_kick_vpn_transition("CN", "CN") is False
    assert vge.should_kick_vpn_transition("US", "US") is False
    assert vge.should_kick_vpn_transition("", "CN") is False
    assert vge.should_kick_vpn_transition("US", None) is False


def test_try_decode_skips_mgat() -> None:
    req = MagicMock()
    req.headers = {"Authorization": "Bearer mgat_abc"}
    req.cookies = {}
    assert vge.try_decode_access_token_payload(req) is None


def test_maybe_enforce_kicks_when_login_non_cn() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.get = MagicMock(return_value=pipe)
    pipe.execute = MagicMock(return_value=[b"US", b"203.0.113.1"])
    redis.pipeline = MagicMock(return_value=pipe)

    sess_mgr = MagicMock()
    refresh_mgr = MagicMock()
    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    req.headers = {}
    req.cookies = {"access_token": "valid.jwt"}

    with patch.object(vge, "VPN_CN_KICKOUT_ALLOWLIST_USER_IDS", set()):
        with patch.object(vge, "AUTH_MODE", "standard"):
            with patch.object(vge, "VPN_CN_KICKOUT_ENABLED", True):
                with patch.object(vge, "is_redis_available", return_value=True):
                    with patch.object(vge, "get_redis", return_value=redis):
                        with patch.object(vge, "get_session_manager", return_value=sess_mgr):
                            with patch.object(vge, "get_refresh_token_manager", return_value=refresh_mgr):
                                with patch.object(
                                    vge,
                                    "resolve_country_iso_from_request",
                                    return_value="CN",
                                ):
                                    with patch.object(vge, "get_client_ip", return_value="203.0.113.9"):
                                        with patch.object(
                                            vge,
                                            "try_decode_access_token_payload",
                                            return_value={"sub": "1", "phone": "", "type": "access"},
                                        ):
                                            with patch.object(vge, "json_forbidden_cn_geo") as jfg:
                                                jfg.return_value = MagicMock(status_code=403)
                                                out = vge.maybe_enforce_vpn_cn_geo(req)

    assert out is not None
    sess_mgr.invalidate_user_sessions.assert_called_once()
    refresh_mgr.revoke_all_refresh_tokens.assert_called_once_with(1, reason="vpn_cn_geo")


def test_maybe_enforce_fast_path_same_ip_no_resolve() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = MagicMock(return_value=[b"US", b"8.8.8.8"])
    pipe.expire.return_value = pipe
    redis.pipeline = MagicMock(return_value=pipe)

    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    req.headers = {}
    req.cookies = {}

    with patch.object(vge, "VPN_CN_KICKOUT_ALLOWLIST_USER_IDS", set()):
        with patch.object(vge, "AUTH_MODE", "standard"):
            with patch.object(vge, "VPN_CN_KICKOUT_ENABLED", True):
                with patch.object(vge, "is_redis_available", return_value=True):
                    with patch.object(vge, "get_redis", return_value=redis):
                        with patch.object(vge, "resolve_country_iso_from_request") as resolve_mock:
                            with patch.object(vge, "get_client_ip", return_value="8.8.8.8"):
                                with patch.object(
                                    vge,
                                    "try_decode_access_token_payload",
                                    return_value={"sub": "2", "phone": "", "type": "access"},
                                ):
                                    out = vge.maybe_enforce_vpn_cn_geo(req)

    assert out is None
    resolve_mock.assert_not_called()
    assert pipe.expire.call_count == 2


@patch.object(vge, "VPN_CN_KICKOUT_ENABLED", True)
@patch.object(vge, "AUTH_MODE", "standard")
def test_maybe_enforce_skips_cn_mobile_phone() -> None:
    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    payload = {"sub": "3", "phone": "13800138000", "type": "access"}
    with patch.object(vge, "try_decode_access_token_payload", return_value=payload):
        assert vge.maybe_enforce_vpn_cn_geo(req) is None


async def test_maybe_enforce_async_prefers_request_state_user() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.get = MagicMock(return_value=pipe)
    pipe.execute = MagicMock(return_value=[b"US", b"203.0.113.1"])
    redis.pipeline = MagicMock(return_value=pipe)

    sess_mgr = MagicMock()
    refresh_mgr = MagicMock()
    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    req.headers = {"Authorization": "Bearer mgat_x", "X-MG-Account": "8613800138000"}
    req.cookies = {}
    req.state = SimpleNamespace()
    state_user = MagicMock()
    state_user.id = 42
    state_user.phone = ""
    setattr(req.state, AUTH_CONTEXT_USER_ATTR, state_user)

    with patch.object(vge, "VPN_CN_KICKOUT_ALLOWLIST_USER_IDS", set()):
        with patch.object(vge, "AUTH_MODE", "standard"):
            with patch.object(vge, "VPN_CN_KICKOUT_ENABLED", True):
                with patch.object(
                    vge,
                    "maybe_enforce_email_login_cn_geo_api_async",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    with patch.object(vge, "is_redis_available", return_value=True):
                        with patch.object(vge, "get_redis", return_value=redis):
                            with patch.object(vge, "get_session_manager", return_value=sess_mgr):
                                with patch.object(vge, "get_refresh_token_manager", return_value=refresh_mgr):
                                    with patch.object(
                                        vge,
                                        "resolve_country_iso_from_request",
                                        return_value="CN",
                                    ):
                                        with patch.object(vge, "get_client_ip", return_value="203.0.113.9"):
                                            with patch.object(
                                                vge,
                                                "validate_user_token",
                                                new_callable=AsyncMock,
                                            ) as vut:
                                                with patch.object(vge, "json_forbidden_cn_geo") as jfg:
                                                    jfg.return_value = MagicMock(status_code=403)
                                                    out = await vge.maybe_enforce_vpn_cn_geo_async(req)

    assert out is not None
    vut.assert_not_called()
    refresh_mgr.revoke_all_refresh_tokens.assert_called_once_with(42, reason="vpn_cn_geo")


async def test_maybe_enforce_async_mgat_kicks_when_login_non_cn() -> None:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.get = MagicMock(return_value=pipe)
    pipe.execute = MagicMock(return_value=[b"US", b"203.0.113.1"])
    redis.pipeline = MagicMock(return_value=pipe)

    sess_mgr = MagicMock()
    refresh_mgr = MagicMock()
    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    req.headers = {"Authorization": "Bearer mgat_x", "X-MG-Account": "8613800138000"}
    req.cookies = {}
    req.state = SimpleNamespace()

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.phone = "8613800138000"

    with patch.object(vge, "VPN_CN_KICKOUT_ALLOWLIST_USER_IDS", set()):
        with patch.object(vge, "AUTH_MODE", "standard"):
            with patch.object(vge, "VPN_CN_KICKOUT_ENABLED", True):
                with patch.object(
                    vge,
                    "maybe_enforce_email_login_cn_geo_api_async",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    with patch.object(vge, "is_redis_available", return_value=True):
                        with patch.object(vge, "get_redis", return_value=redis):
                            with patch.object(vge, "get_session_manager", return_value=sess_mgr):
                                with patch.object(vge, "get_refresh_token_manager", return_value=refresh_mgr):
                                    with patch.object(
                                        vge,
                                        "resolve_country_iso_from_request",
                                        return_value="CN",
                                    ):
                                        with patch.object(vge, "get_client_ip", return_value="203.0.113.9"):
                                            with patch.object(
                                                vge,
                                                "try_decode_access_token_payload",
                                                return_value=None,
                                            ):
                                                with patch.object(
                                                    vge,
                                                    "validate_user_token",
                                                    new_callable=AsyncMock,
                                                    return_value=mock_user,
                                                ):
                                                    with patch.object(vge, "json_forbidden_cn_geo") as jfg:
                                                        jfg.return_value = MagicMock(status_code=403)
                                                        out = await vge.maybe_enforce_vpn_cn_geo_async(req)

    assert out is not None
    sess_mgr.invalidate_user_sessions.assert_called_once()
    refresh_mgr.revoke_all_refresh_tokens.assert_called_once_with(1, reason="vpn_cn_geo")


async def test_maybe_enforce_async_mgat_without_account_skips() -> None:
    req = MagicMock()
    req.url.path = "/api/foo"
    req.method = "GET"
    req.headers = {"Authorization": "Bearer mgat_x"}
    req.cookies = {}
    req.state = SimpleNamespace()

    with patch.object(vge, "VPN_CN_KICKOUT_ENABLED", True):
        with patch.object(vge, "AUTH_MODE", "standard"):
            with patch.object(
                vge,
                "maybe_enforce_email_login_cn_geo_api_async",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with patch.object(vge, "try_decode_access_token_payload", return_value=None):
                    out = await vge.maybe_enforce_vpn_cn_geo_async(req)

    assert out is None
