"""Tests for org+code index fast path and force-burn fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.auth.dingtalk_bind_redis import (
    force_burn_bind_token,
    register_bind_code_index,
    resolve_bind_token_for_org_code,
)
from services.auth.quick_register_room_code import current_room_code_from_room_secret


@pytest.mark.asyncio
async def test_resolve_uses_code_index_before_org_scan() -> None:
    """Code index resolves without scanning the full org token set."""
    secret = "index-secret"
    token = "index-token-abc"
    code, _, _, _ = current_room_code_from_room_secret(secret, token)

    async def fake_get_bind_token_data(stripped: str):
        if stripped != token:
            return None
        return {
            "user_id": 1,
            "organization_id": 5,
            "bind_code_secret": secret,
        }

    redis = AsyncMock()

    async def smembers_side(key: str | bytes) -> set[str]:
        key_text = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        if key_text.startswith("dingtalk_bind:ocode:5:"):
            return {token}
        return set()

    redis.smembers = AsyncMock(side_effect=smembers_side)

    with (
        patch("services.auth.dingtalk_bind_redis.get_async_redis", return_value=redis),
        patch(
            "services.auth.dingtalk_bind_redis.get_bind_token_data",
            side_effect=fake_get_bind_token_data,
        ),
    ):
        resolved = await resolve_bind_token_for_org_code(5, code)

    assert resolved == token
    org_scan_calls = [
        call.args[0] for call in redis.smembers.await_args_list if str(call.args[0]).startswith("dingtalk_bind:org:")
    ]
    assert org_scan_calls == []


@pytest.mark.asyncio
async def test_register_bind_code_index_writes_skew_windows() -> None:
    """Registering a session indexes current and adjacent time steps."""
    secret = "register-secret"
    token = "register-token"
    redis = AsyncMock()
    pipe = MagicMock()
    pipe.sadd = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline = MagicMock(return_value=pipe)

    with patch("services.auth.dingtalk_bind_redis.get_async_redis", return_value=redis):
        await register_bind_code_index(organization_id=5, token=token, bind_secret=secret)

    assert pipe.sadd.call_count == 3
    assert pipe.expire.call_count == 3


@pytest.mark.asyncio
async def test_force_burn_bind_token_marks_consumed_when_consume_fails() -> None:
    """Force-burn deletes token and sets consumed marker."""
    token = "burn-me"
    payload = {"user_id": 7, "organization_id": 5, "bind_code_secret": "x"}
    redis = AsyncMock()
    pipe = MagicMock()
    pipe.set = MagicMock(return_value=pipe)
    pipe.delete = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline = MagicMock(return_value=pipe)

    with (
        patch("services.auth.dingtalk_bind_redis.get_async_redis", return_value=redis),
        patch(
            "services.auth.dingtalk_bind_redis.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.auth.dingtalk_bind_redis.consume_bind_token",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.auth.dingtalk_bind_redis.get_bind_token_data",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.auth.dingtalk_bind_redis._remove_token_from_org_index",
            new_callable=AsyncMock,
        ),
    ):
        burned = await force_burn_bind_token(token)

    assert burned is True
    pipe.set.assert_called_once()
    pipe.delete.assert_called_once()
