"""Tests for org-scoped bind token resolution by rotating code."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.auth.dingtalk_bind_redis import resolve_bind_token_for_org_code
from services.auth.quick_register_room_code import current_room_code_from_room_secret


@pytest.mark.asyncio
async def test_resolve_bind_token_for_org_code_matches_pending_session() -> None:
    """Org index resolves the token whose HMAC code matches."""
    secret = "per-token-secret"
    token = "channel-token-xyz"
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
    org_key = "dingtalk_bind:org:5"

    async def smembers_side(key: str | bytes) -> set[str]:
        key_text = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        if key_text == org_key:
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


@pytest.mark.asyncio
async def test_resolve_bind_token_for_org_code_returns_none_when_no_match() -> None:
    """Empty org index yields no token."""
    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())

    with patch("services.auth.dingtalk_bind_redis.get_async_redis", return_value=redis):
        resolved = await resolve_bind_token_for_org_code(5, "123456")

    assert resolved is None
