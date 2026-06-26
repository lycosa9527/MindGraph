"""Tests for refresh-token reuse detection (rotated token presented again)."""

from unittest.mock import AsyncMock, patch

import pytest

from services.redis.session.redis_session_manager import RefreshTokenManager


@pytest.mark.asyncio
async def test_validate_refresh_token_reuse_triggers_session_revocation() -> None:
    """Presenting a rotated refresh token revokes all user sessions."""
    mgr = RefreshTokenManager()
    user_id = 42
    token_hash = "abc123deadbeef"

    with patch.object(mgr, "_use_redis", return_value=True):
        with patch(
            "services.redis.session.redis_session_manager.AsyncRedisOps.get",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.side_effect = [None, str(user_id)]
            with patch.object(
                mgr,
                "_handle_refresh_token_reuse",
                new_callable=AsyncMock,
            ) as mock_reuse:
                valid, _data, error = await mgr.validate_refresh_token(
                    user_id=user_id,
                    token_hash=token_hash,
                )

    assert valid is False
    assert error == "Session invalidated due to token reuse"
    mock_reuse.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_revoke_refresh_token_sets_reuse_marker_before_delete() -> None:
    """Revocation stores a reuse marker so replay can be detected."""
    mgr = RefreshTokenManager()
    token_hash = "rotatedhash"

    mock_redis = AsyncMock()
    mock_redis.srem = AsyncMock()

    with patch.object(mgr, "_use_redis", return_value=True):
        with patch(
            "services.redis.session.redis_session_manager.get_async_redis",
            return_value=mock_redis,
        ):
            with patch(
                "services.redis.session.redis_session_manager.AsyncRedisOps.set_with_ttl",
                new_callable=AsyncMock,
            ) as mock_set_ttl:
                with patch(
                    "services.redis.session.redis_session_manager.AsyncRedisOps.delete",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    await mgr.revoke_refresh_token(7, token_hash, reason="rotation")

    mock_set_ttl.assert_awaited_once()
    await_args = mock_set_ttl.await_args
    assert await_args is not None
    assert await_args.args[1] == "7"
