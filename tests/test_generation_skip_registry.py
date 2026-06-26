"""Tests for generate_dingtalk library skip Redis registry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram.generation_skip_registry import (
    GEN_LIB_SKIP_PREFIX,
    get_generation_library_skip,
    get_generation_preview_outcome,
    store_generation_library_skip,
)


@pytest.mark.asyncio
async def test_store_generation_library_skip_success() -> None:
    """Store writes JSON payload with TTL."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    with patch(
        "services.diagram.generation_skip_registry.get_async_redis",
        return_value=redis,
    ):
        ok = await store_generation_library_skip(
            "deadbeef",
            reason="unbound_staff",
            language="zh",
        )
    assert ok is True
    redis.set.assert_awaited_once()
    key_arg = redis.set.await_args.args[0]
    assert key_arg == f"{GEN_LIB_SKIP_PREFIX}deadbeef"
    payload = redis.set.await_args.args[1]
    assert "unbound_staff" in payload
    assert "zh" in payload


@pytest.mark.asyncio
async def test_store_generation_library_skip_no_redis() -> None:
    """Returns False when Redis unavailable."""
    with patch(
        "services.diagram.generation_skip_registry.get_async_redis",
        return_value=None,
    ):
        ok = await store_generation_library_skip("abc", reason="no_user", language="en")
    assert ok is False


@pytest.mark.asyncio
async def test_get_generation_library_skip_roundtrip() -> None:
    """Get returns parsed reason and language."""
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value='{"reason":"save_error","language":"en"}',
    )
    with patch(
        "services.diagram.generation_skip_registry.get_async_redis",
        return_value=redis,
    ):
        data = await get_generation_library_skip("abc12345")
    assert data == {"reason": "save_error", "language": "en"}


@pytest.mark.asyncio
async def test_get_generation_library_skip_success_outcome() -> None:
    """Saved diagram id is returned even when reason is empty."""
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value='{"reason":"","language":"zh","diagram_id":"abc-123"}',
    )
    with patch(
        "services.diagram.generation_skip_registry.get_async_redis",
        return_value=redis,
    ):
        data = await get_generation_library_skip("abc12345")
    assert data == {"reason": "", "language": "zh", "diagram_id": "abc-123"}


@pytest.mark.asyncio
async def test_get_generation_preview_outcome_db_fallback() -> None:
    """When Redis misses, load durable preview metadata from PostgreSQL."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    link = MagicMock()
    link.diagram_id = "550e8400-e29b-41d4-a716-446655440000"
    link.skip_reason = ""
    link.language = "zh"
    link.diagram_type = "bubble_map"
    link.title = "Test"
    link.spec = None
    repo = MagicMock()
    repo.get_by_preview_id = AsyncMock(return_value=link)
    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    with (
        patch(
            "services.diagram.generation_skip_registry.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.diagram.generation_skip_registry.system_rls_session",
            return_value=session_cm,
        ),
        patch(
            "services.diagram.generation_skip_registry.GenerationPreviewLinkRepository",
            return_value=repo,
        ),
    ):
        data = await get_generation_preview_outcome("deadbeef")
    assert data is not None
    assert data["diagram_id"] == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_get_generation_library_skip_missing() -> None:
    """Missing key returns None."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    with patch(
        "services.diagram.generation_skip_registry.get_async_redis",
        return_value=redis,
    ):
        data = await get_generation_library_skip("missing1")
    assert data is None
