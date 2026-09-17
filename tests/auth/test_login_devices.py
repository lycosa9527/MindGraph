"""Unit tests for account login-device list and kick."""

from unittest.mock import AsyncMock, patch

import pytest

from services.auth.login_devices import (
    LoginDevice,
    LoginDevicesUnavailableError,
    describe_user_agent,
    is_login_device_id,
    kick_login_device,
    list_login_devices,
    login_device_to_dict,
    merge_login_device_rows,
)


def test_describe_user_agent_chrome_windows() -> None:
    """Chrome on Windows becomes a short label."""
    label = describe_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    assert label == "Chrome · Windows"


def test_describe_user_agent_safari_ios() -> None:
    """Mobile Safari is labeled Safari on iOS."""
    label = describe_user_agent(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    )
    assert label == "Safari · iOS"


def test_describe_user_agent_empty() -> None:
    """Missing User-Agent yields an empty label."""
    assert describe_user_agent("") == ""


def test_is_login_device_id_accepts_hex() -> None:
    """Device fingerprints are 8–64 hex characters."""
    assert is_login_device_id("ab" * 8)
    assert not is_login_device_id("short")
    assert not is_login_device_id("../etc/passwd")


def test_merge_puts_current_first_and_keeps_refresh_metadata() -> None:
    """Current device is first; refresh UA/IP win over access-only rows."""
    devices = merge_login_device_rows(
        [
            {
                "device_hash": "aaaabbbbccccdddd",
                "user_agent": "Mozilla/5.0 (Macintosh) Chrome/128.0.0.0 Safari/537.36",
                "ip_address": "203.0.113.9",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "device_hash": "1111222233334444",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0) Firefox/140.0",
                "ip_address": "198.51.100.4",
                "created_at": "2026-02-01T00:00:00+00:00",
            },
        ],
        [
            {
                "device_hash": "aaaabbbbccccdddd",
                "created_at": "2026-03-01T00:00:00+00:00",
            }
        ],
        "aaaabbbbccccdddd",
    )
    assert [item.device_id for item in devices] == ["aaaabbbbccccdddd", "1111222233334444"]
    assert devices[0].is_current is True
    assert devices[0].label == "Chrome · macOS"
    assert devices[0].ip_address == "203.0.113.9"
    assert devices[0].created_at == "2026-03-01T00:00:00+00:00"
    assert devices[1].is_current is False


def test_login_device_to_dict_includes_current_flag() -> None:
    """API payload keeps the current-device flag."""
    payload = login_device_to_dict(
        LoginDevice(
            device_id="abcd" * 4,
            label="Chrome · Windows",
            ip_address="203.0.113.1",
            created_at="2026-01-01T00:00:00+00:00",
            is_current=True,
        )
    )
    assert payload["is_current"] is True
    assert payload["device_id"] == "abcd" * 4


@pytest.mark.asyncio
async def test_list_login_devices_raises_when_redis_down() -> None:
    """Both Redis views None means the account UI cannot load devices."""
    refresh = AsyncMock()
    refresh.list_refresh_records = AsyncMock(return_value=None)
    session = AsyncMock()
    session.list_access_session_devices = AsyncMock(return_value=None)
    with patch(
        "services.auth.login_devices.get_refresh_token_manager",
        return_value=refresh,
    ):
        with patch(
            "services.auth.login_devices.get_session_manager",
            return_value=session,
        ):
            with pytest.raises(LoginDevicesUnavailableError):
                await list_login_devices(7, "abcd" * 4)


@pytest.mark.asyncio
async def test_kick_login_device_revokes_refresh_and_access() -> None:
    """Kick must revoke refresh tokens and invalidate access sessions."""
    refresh = AsyncMock()
    refresh.list_refresh_records = AsyncMock(
        return_value=[{"device_hash": "abcd" * 4, "user_agent": "", "ip_address": "", "created_at": ""}]
    )
    refresh.revoke_refresh_tokens_for_device = AsyncMock(return_value=1)
    session = AsyncMock()
    session.list_access_session_devices = AsyncMock(return_value=[])
    session.invalidate_sessions_for_device = AsyncMock(return_value=1)
    with patch(
        "services.auth.login_devices.get_refresh_token_manager",
        return_value=refresh,
    ):
        with patch(
            "services.auth.login_devices.get_session_manager",
            return_value=session,
        ):
            kicked = await kick_login_device(7, "abcd" * 4, "203.0.113.8")
    assert kicked is True
    refresh.revoke_refresh_tokens_for_device.assert_awaited_once_with(
        7,
        "abcd" * 4,
        reason="device_kick",
    )
    session.invalidate_sessions_for_device.assert_awaited_once_with(
        7,
        "abcd" * 4,
        ip_address="203.0.113.8",
        reason="device_kick",
    )


@pytest.mark.asyncio
async def test_kick_unknown_device_is_false() -> None:
    """Unknown device ids are not revoked."""
    refresh = AsyncMock()
    refresh.list_refresh_records = AsyncMock(return_value=[])
    refresh.revoke_refresh_tokens_for_device = AsyncMock(return_value=0)
    session = AsyncMock()
    session.list_access_session_devices = AsyncMock(return_value=[])
    with patch(
        "services.auth.login_devices.get_refresh_token_manager",
        return_value=refresh,
    ):
        with patch(
            "services.auth.login_devices.get_session_manager",
            return_value=session,
        ):
            kicked = await kick_login_device(7, "ffff" * 4, "203.0.113.8")
    assert kicked is False
    refresh.revoke_refresh_tokens_for_device.assert_not_awaited()
