"""End-to-end contract for max-device kick-off: new login keeps the slot."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routers.auth.session import (
    get_session_status,
    refresh_token as refresh_token_endpoint,
    router as session_router,
)
from services.redis.session.redis_session_manager import (
    RefreshTokenManager,
    RedisSessionManager,
    select_oldest_refresh_hashes_to_revoke,
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


def test_eviction_fifo_successive_logins_kick_oldest_then_next() -> None:
    """Limit 2: C kicks A, then D kicks B. The newest login always stays."""
    device_a = "1000.0:deva:hasha"
    device_b = "2000.0:devb:hashb"
    device_c = "3000.0:devc:hashc"
    device_d = "4000.0:devd:hashd"

    after_c = [device_a, device_b, device_c]
    kicked_by_c = select_oldest_sessions_to_evict(after_c, device_c, max_sessions=2)
    assert kicked_by_c == [device_a]
    remaining = [entry for entry in after_c if entry not in kicked_by_c]
    assert remaining == [device_b, device_c]

    after_d = [*remaining, device_d]
    kicked_by_d = select_oldest_sessions_to_evict(after_d, device_d, max_sessions=2)
    assert kicked_by_d == [device_b]
    remaining = [entry for entry in after_d if entry not in kicked_by_d]
    assert remaining == [device_c, device_d]
    assert device_d not in kicked_by_d


def test_eviction_drops_every_excess_oldest_when_already_over_limit() -> None:
    """Lowering the cap (or leftover rows) still keeps the new login plus the newest old one."""
    new_entry = "5000.0:neve:newhash"
    entries = [
        "1000.0:deva:hasha",
        "2000.0:devb:hashb",
        "3000.0:devc:hashc",
        "4000.0:devd:hashd",
        new_entry,
    ]
    evicted = select_oldest_sessions_to_evict(entries, new_entry, max_sessions=2)
    assert evicted == [
        "1000.0:deva:hasha",
        "2000.0:devb:hashb",
        "3000.0:devc:hashc",
    ]
    assert new_entry not in evicted


def test_refresh_fifo_successive_logins_revoke_oldest_then_next() -> None:
    """Refresh tokens follow the same FIFO as access sessions."""
    tokens = [
        ("old_a", "2026-01-01T00:00:00+00:00"),
        ("old_b", "2026-01-02T00:00:00+00:00"),
        ("new_c", "2026-01-03T00:00:00+00:00"),
    ]
    first = select_oldest_refresh_hashes_to_revoke(tokens, "new_c", max_sessions=2)
    assert first == ["old_a"]
    remaining = [(token_hash, created_at) for token_hash, created_at in tokens if token_hash not in first]
    remaining.append(("new_d", "2026-01-04T00:00:00+00:00"))
    second = select_oldest_refresh_hashes_to_revoke(remaining, "new_d", max_sessions=2)
    assert second == ["old_b"]
    kept = [token_hash for token_hash, _created in remaining if token_hash not in second]
    assert kept == ["new_c", "new_d"]


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
async def test_store_session_revokes_each_excess_oldest_device() -> None:
    """When already over the cap, every excess oldest device is kicked, not just one."""
    mgr = RedisSessionManager()
    evicted = ["1000.0:olda:hasha", "2000.0:oldb:hashb"]
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.eval = AsyncMock(return_value=evicted)
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
                    stored = await mgr.store_session(4, "new-access-jwt", device_hash="newdevice")

    assert stored is True
    assert notify.await_args_list == [
        ((4, "hasha"),),
        ((4, "hashb"),),
    ]
    assert refresh.revoke_refresh_tokens_for_device.await_args_list == [
        ((4, "olda"),),
        ((4, "oldb"),),
    ]


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


@pytest.mark.asyncio
async def test_session_status_no_token_is_not_a_kick() -> None:
    """Missing cookies must not look like a device-limit logout."""
    request = MagicMock()
    request.cookies = {}
    request.headers = {}

    result = await get_session_status(request, x_language=None)

    assert result == {"status": "unauthenticated"}


@pytest.mark.asyncio
async def test_refresh_rejects_kicked_access_without_reuse_check() -> None:
    """A kicked device must not rotate back in or trigger reuse revocation."""
    request = MagicMock()
    request.cookies = {"access_token": "kicked-jwt", "refresh_token": "old-refresh"}
    request.headers = {}
    response = MagicMock()
    refresh_mgr = AsyncMock()
    refresh_mgr.find_user_id_from_token = AsyncMock(return_value=42)
    refresh_mgr.validate_refresh_token = AsyncMock()
    session_mgr = AsyncMock()
    session_mgr.check_invalidation_notification = AsyncMock(
        return_value={"timestamp": "2026-01-01T00:00:00+00:00", "ip_address": "10.0.0.1"}
    )
    limiter = AsyncMock()
    limiter.check_and_record = AsyncMock(return_value=(True, 1, 0))

    with patch("routers.auth.session.get_client_ip", return_value="10.0.0.1"):
        with patch("routers.auth.session.get_rate_limiter", return_value=limiter):
            with patch("routers.auth.session.hash_refresh_token", return_value="oldhash"):
                with patch("routers.auth.session.get_refresh_token_manager", return_value=refresh_mgr):
                    with patch("routers.auth.session.get_session_manager", return_value=session_mgr):
                        with pytest.raises(HTTPException) as exc_info:
                            await refresh_token_endpoint(request, response)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session ended: maximum device limit exceeded"
    refresh_mgr.validate_refresh_token.assert_not_called()


def _session_http_client() -> TestClient:
    """HTTP client for session routes only (no app lifespan / Celery)."""
    app = FastAPI()
    app.include_router(session_router, prefix="/api/auth")
    return TestClient(app)


def test_http_session_status_without_cookie_is_unauthenticated() -> None:
    """Anonymous GET must not return the kick-off 'Session invalidated' string."""
    response = _session_http_client().get("/api/auth/session-status")
    assert response.status_code == 200
    assert response.json() == {"status": "unauthenticated"}


def test_http_refresh_without_cookie_is_401() -> None:
    """Overnight access expiry still needs a refresh cookie to stay signed in."""
    response = _session_http_client().post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "No refresh token provided"
