"""End-to-end contract for max-device kick-off: new login keeps the slot."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.auth.session import get_session_status
from services.redis.session.redis_session_manager import (
    RefreshTokenManager,
    RedisSessionManager,
    select_oldest_sessions_to_evict,
)


def test_eviction_drops_oldest_and_keeps_new_device() -> None:
    """Third device login evicts the oldest of the two already logged in."""
    new_entry = "3000.0:newdev:newhash"
    entries = [
        "1000.0:olda:oldahash",
        "2000.0:oldb:oldbhash",
        new_entry,
    ]
    evicted = select_oldest_sessions_to_evict(entries, new_entry, max_sessions=2)
    assert evicted == ["1000.0:olda:oldahash"]
    assert new_entry not in evicted


def test_eviction_never_drops_new_entry_when_timestamp_is_oldest() -> None:
    """Clock skew or a malformed prefix must not kick the device that just logged in."""
    new_entry = "100.0:newdev:newhash"
    entries = [
        "500.0:olda:oldahash",
        "600.0:oldb:oldbhash",
        new_entry,
    ]
    evicted = select_oldest_sessions_to_evict(entries, new_entry, max_sessions=2)
    assert new_entry not in evicted
    assert evicted == ["500.0:olda:oldahash"]


def test_eviction_keeps_new_entry_when_max_sessions_is_zero() -> None:
    """A misconfigured limit of 0 still lets the new device in."""
    new_entry = "9.0:newdev:newhash"
    evicted = select_oldest_sessions_to_evict(
        ["1.0:olda:oldahash", new_entry],
        new_entry,
        max_sessions=0,
    )
    assert evicted == ["1.0:olda:oldahash"]
    assert new_entry not in evicted


@pytest.mark.asyncio
async def test_store_session_revokes_refresh_for_evicted_device() -> None:
    """Access eviction and refresh revocation must target the same old device."""
    mgr = RedisSessionManager()
    evicted = "1000.0:olddevicehash:oldtokenhash"
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.eval = AsyncMock(return_value=[evicted])
    refresh = AsyncMock()
    refresh.revoke_refresh_tokens_for_device = AsyncMock(return_value=1)

    with patch.object(mgr, "_use_redis", return_value=True):
        with patch(
            "services.redis.session.redis_session_manager.get_async_redis",
            return_value=mock_redis,
        ):
            with patch(
                "services.redis.session.redis_session_manager.get_refresh_token_manager",
                return_value=refresh,
            ):
                with patch.object(mgr, "notify_invalidation", new_callable=AsyncMock) as notify:
                    stored = await mgr.store_session(7, "new-access-jwt", device_hash="newdevice")

    assert stored is True
    notify.assert_awaited_once_with(7, "oldtokenhash")
    refresh.revoke_refresh_tokens_for_device.assert_awaited_once_with(7, "olddevicehash")


@pytest.mark.asyncio
async def test_store_session_single_eval_string_is_one_entry() -> None:
    """A one-element Redis EVAL return must not be iterated as characters."""
    mgr = RedisSessionManager()
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.eval = AsyncMock(return_value="1000.0:olddevicehash:oldtokenhash")
    refresh = AsyncMock()
    refresh.revoke_refresh_tokens_for_device = AsyncMock(return_value=1)

    with patch.object(mgr, "_use_redis", return_value=True):
        with patch(
            "services.redis.session.redis_session_manager.get_async_redis",
            return_value=mock_redis,
        ):
            with patch(
                "services.redis.session.redis_session_manager.get_refresh_token_manager",
                return_value=refresh,
            ):
                with patch.object(mgr, "notify_invalidation", new_callable=AsyncMock) as notify:
                    stored = await mgr.store_session(3, "new-access-jwt", device_hash="newdevice")

    assert stored is True
    notify.assert_awaited_once_with(3, "oldtokenhash")
    refresh.revoke_refresh_tokens_for_device.assert_awaited_once_with(3, "olddevicehash")


@pytest.mark.asyncio
async def test_kick_revoke_uses_max_devices_reason() -> None:
    """Max-device kick must not be audited as a same-device relogin."""
    mgr = RefreshTokenManager()
    with patch.object(mgr, "_revoke_existing_device_tokens", new_callable=AsyncMock) as revoke:
        await mgr.revoke_refresh_tokens_for_device(1, "abc")
    revoke.assert_awaited_once_with(1, "abc", reason="max_devices_exceeded")


@pytest.mark.asyncio
async def test_enforce_max_tokens_never_revokes_protected_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refresh token created for the new login must survive FIFO eviction."""
    monkeypatch.setattr(
        "services.redis.session.redis_session_manager.MAX_CONCURRENT_SESSIONS",
        2,
    )
    mgr = RefreshTokenManager()
    token_json = {
        "old_a": '{"created_at": "2026-01-01T00:00:00+00:00", "device_hash": "a"}',
        "old_b": '{"created_at": "2026-01-02T00:00:00+00:00", "device_hash": "b"}',
        "new_c": '{"created_at": "2026-01-01T00:00:00+00:00", "device_hash": "c"}',
    }
    mock_redis = AsyncMock()
    mock_redis.scard = AsyncMock(return_value=3)
    mock_redis.smembers = AsyncMock(return_value=set(token_json))

    async def _get(key: str) -> str | None:
        for token_hash, payload in token_json.items():
            if key.endswith(token_hash):
                return payload
        return None

    revoked: list[str] = []

    async def _revoke(_user_id: int, token_hash: bytes | str, reason: str = "") -> bool:
        revoked.append(str(token_hash))
        assert reason == "max_devices_exceeded"
        return True

    with patch.object(mgr, "_use_redis", return_value=True):
        with patch(
            "services.redis.session.redis_session_manager.get_async_redis",
            return_value=mock_redis,
        ):
            with patch(
                "services.redis.session.redis_session_manager.AsyncRedisOps.get",
                side_effect=_get,
            ):
                with patch.object(mgr, "revoke_refresh_token", side_effect=_revoke):
                    count = await mgr.enforce_max_tokens(9, protect_token_hash="new_c")

    assert count == 1
    assert revoked == ["old_a"]
    assert "new_c" not in revoked


@pytest.mark.asyncio
async def test_session_status_reads_kick_without_live_session() -> None:
    """Kicked devices must see invalidated even though Redis no longer has the token."""
    request = MagicMock()
    request.cookies = {"access_token": "kicked-jwt"}
    request.headers = {}
    mgr = AsyncMock()
    mgr.check_invalidation_notification = AsyncMock(
        return_value={"timestamp": "2026-01-01T00:00:00+00:00", "ip_address": "10.0.0.1"}
    )
    mgr.clear_invalidation_notification = AsyncMock(return_value=True)

    with patch("routers.auth.session.decode_access_token", return_value={"sub": "42"}):
        with patch("routers.auth.session.get_session_manager", return_value=mgr):
            result = await get_session_status(request, x_language=None)

    assert result["status"] == "invalidated"
    assert result["message"] == "Session ended: maximum device limit exceeded"
    mgr.is_session_valid.assert_not_called()
    mgr.clear_invalidation_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_status_active_when_session_still_valid() -> None:
    """The new device must stay active after login."""
    request = MagicMock()
    request.cookies = {"access_token": "fresh-jwt"}
    request.headers = {}
    mgr = AsyncMock()
    mgr.check_invalidation_notification = AsyncMock(return_value=None)
    mgr.is_session_valid = AsyncMock(return_value=True)

    with patch("routers.auth.session.decode_access_token", return_value={"sub": "42"}):
        with patch("routers.auth.session.get_session_manager", return_value=mgr):
            result = await get_session_status(request, x_language=None)

    assert result == {"status": "active"}


@pytest.mark.asyncio
async def test_session_status_401_when_missing_notification_lets_refresh_run() -> None:
    """Without a kick notice, 401 lets the client refresh (rotation race)."""
    request = MagicMock()
    request.cookies = {"access_token": "stale-jwt"}
    request.headers = {}
    mgr = AsyncMock()
    mgr.check_invalidation_notification = AsyncMock(return_value=None)
    mgr.is_session_valid = AsyncMock(return_value=False)

    with patch("routers.auth.session.decode_access_token", return_value={"sub": "42"}):
        with patch("routers.auth.session.get_session_manager", return_value=mgr):
            with pytest.raises(HTTPException) as exc_info:
                await get_session_status(request, x_language=None)

    assert exc_info.value.status_code == 401
