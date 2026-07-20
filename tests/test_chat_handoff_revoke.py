"""Unit tests for chat-handoff pairing revoke helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.knowledge.chat_handoff_service import (
    revoke_handoff_code,
    revoke_waiting_handoffs_for_package,
)


@pytest.mark.asyncio
async def test_revoke_handoff_code_deletes_waiting_owner_code() -> None:
    """Owner can revoke a waiting pairing code."""
    payload = json.dumps({"user_id": 7, "package_id": 3, "status": "waiting", "document_id": None})
    with (
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.get",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.delete",
            new_callable=AsyncMock,
        ) as delete,
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.set_remove",
            new_callable=AsyncMock,
        ) as set_remove,
    ):
        revoked = await revoke_handoff_code("123456", 7)

    assert revoked is True
    delete.assert_awaited_once()
    set_remove.assert_awaited()


@pytest.mark.asyncio
async def test_revoke_handoff_code_skips_non_waiting() -> None:
    """Already-claimed codes are left alone."""
    payload = json.dumps({"user_id": 7, "package_id": 3, "status": "received", "document_id": None})
    with (
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.get",
            new_callable=AsyncMock,
            return_value=payload,
        ),
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.delete",
            new_callable=AsyncMock,
        ) as delete,
    ):
        revoked = await revoke_handoff_code("123456", 7)

    assert revoked is False
    delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_waiting_handoffs_for_package() -> None:
    """Package-scoped revoke removes only matching waiting codes."""
    waiting = json.dumps({"user_id": 7, "package_id": 3, "status": "waiting", "document_id": None})
    other_pkg = json.dumps({"user_id": 7, "package_id": 9, "status": "waiting", "document_id": None})

    async def _get(key: str) -> str | None:
        if key.endswith("111111"):
            return waiting
        if key.endswith("222222"):
            return other_pkg
        return None

    with (
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.set_members",
            new_callable=AsyncMock,
            return_value={"111111", "222222"},
        ),
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.get",
            new_callable=AsyncMock,
            side_effect=_get,
        ),
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.delete",
            new_callable=AsyncMock,
        ) as delete,
        patch(
            "services.knowledge.chat_handoff_service.AsyncRedisOps.set_remove",
            new_callable=AsyncMock,
        ),
    ):
        revoked = await revoke_waiting_handoffs_for_package(7, 3)

    assert revoked == 1
    delete.assert_awaited_once()
