"""Live Redis round-trip: mint a pair session, resolve the code, claim, consume."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from repositories.dingtalk_staff_link_repo import StaffLinkClaimResult
from services.auth.dingtalk_bind_redis import (
    bind_code_secret_from_payload,
    get_bind_token_consumed,
    get_bind_token_data,
    mint_bind_token,
    resolve_bind_token_for_org_code,
    store_bind_token,
)
from services.auth.quick_register_room_code import current_room_code_from_room_secret
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.tools.context import ToolIngressContext
from services.mindbot.tools.handlers.pair_code import PairCodeToolHandler

_TEST_REDIS_URL = "redis://localhost:6379/15"
_USER_ID = 9_261_111
_ORG_ID = 9_261_112
_STAFF_ID = "staff-live-pair"


async def _redis_or_skip() -> aioredis.Redis:
    client = aioredis.from_url(
        _TEST_REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1.5,
        socket_timeout=2.0,
    )
    try:
        await client.ping()
    except (OSError, RedisError) as exc:
        await client.aclose()
        pytest.skip(f"Redis not reachable for live DingTalk bind test: {exc}")
    await client.flushdb()
    return client


@asynccontextmanager
async def _db_session(_ctx: object) -> AsyncIterator[MagicMock]:
    db = MagicMock()
    db.commit = AsyncMock()
    yield db


def _ingress(text: str) -> ToolIngressContext:
    return ToolIngressContext(
        cfg=MagicMock(organization_id=_ORG_ID),
        body={"msgtype": "text", "text": {"content": text}},
        inbound_msg_type="text",
        text_in=text,
        sender_staff_id=_STAFF_ID,
        session_webhook_valid="https://example.com/hook",
        session_webhook_pinned_ip="",
        pipeline_ctx="live-pair",
        record_usage=AsyncMock(),
        hdr_for_code=MagicMock(return_value={}),
    )


@pytest.mark.asyncio
async def test_live_pair_code_resolves_claims_and_is_consumed() -> None:
    """MindBot text of the current code claims the Redis session and burns it."""
    client = await _redis_or_skip()
    repo = MagicMock()
    repo.get_by_staff = AsyncMock(return_value=None)
    repo.claim_staff_link = AsyncMock(return_value=StaffLinkClaimResult(ok=True))
    usage = MagicMock()
    usage.backfill_linked_user = AsyncMock()
    finish = AsyncMock(return_value=(200, {}))
    try:
        with (
            patch("services.auth.dingtalk_bind_redis.get_async_redis", return_value=client),
            patch("services.auth.dingtalk_bind_service.rls_async_session", _db_session),
            patch(
                "services.auth.dingtalk_bind_service.DingtalkStaffLinkRepository",
                return_value=repo,
            ),
            patch(
                "services.auth.dingtalk_bind_service.MindbotUsageRepository",
                return_value=usage,
            ),
            patch(
                "services.mindbot.tools.handlers.pair_code.finish_pair_reply",
                finish,
            ),
        ):
            token = mint_bind_token()
            stored = await store_bind_token(
                token=token,
                user_id=_USER_ID,
                organization_id=_ORG_ID,
            )
            assert stored is True
            payload = await get_bind_token_data(token)
            assert payload is not None
            secret = bind_code_secret_from_payload(payload)
            code, _, _, _ = current_room_code_from_room_secret(secret, token)
            assert await resolve_bind_token_for_org_code(_ORG_ID, code) == token
            assert await resolve_bind_token_for_org_code(_ORG_ID, "000000") is None

            display = f"{code[:3]}-{code[3:]}"
            handler = PairCodeToolHandler()
            ctx = _ingress(display)
            assert handler.matches(ctx) is True
            result = await handler.handle(ctx)
            assert result == (200, {})
            assert await get_bind_token_data(token) is None
            assert await get_bind_token_consumed(token) is True
            assert await resolve_bind_token_for_org_code(_ORG_ID, code) is None

        assert finish.await_args is not None
        assert finish.await_args.args[7] == MindbotErrorCode.BIND_OK
        repo.claim_staff_link.assert_awaited_once()
        assert repo.claim_staff_link.await_args is not None
        assert repo.claim_staff_link.await_args.kwargs["linked_via"] == "code_bind"
        usage.backfill_linked_user.assert_awaited_once()
    finally:
        await client.flushdb()
        await client.aclose()
