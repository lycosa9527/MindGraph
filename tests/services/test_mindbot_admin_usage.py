"""Tests for MindBot admin usage serialization and repository list."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.mindbot_usage_repo import MindbotUsageRepository
from routers.api.mindbot import MindbotUsageEventItem


def test_mindbot_usage_event_item_from_simple_namespace() -> None:
    created = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    row = SimpleNamespace(
        id=1,
        organization_id=10,
        mindbot_config_id=20,
        dingtalk_staff_id="staff1",
        sender_nick="Nick",
        dingtalk_sender_id="did1",
        dify_user_key="user-key",
        msg_id="m1",
        dingtalk_conversation_id="dc1",
        dify_conversation_id="df1",
        error_code="MINDBOT_OK",
        streaming=False,
        prompt_chars=3,
        reply_chars=5,
        duration_seconds=1.5,
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        dingtalk_chat_scope="oto",
        inbound_msg_type="text",
        conversation_user_turn=1,
        linked_user_id=None,
        created_at=created,
    )
    item = MindbotUsageEventItem.model_validate(row)
    assert item.id == 1
    assert item.organization_id == 10
    assert item.dingtalk_staff_id == "staff1"
    assert item.created_at == created


@pytest.mark.asyncio
async def test_mindbot_usage_repository_get_event_by_id_calls_execute() -> None:
    session = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=fake_result)

    repo = MindbotUsageRepository(session)
    out = await repo.get_event_by_id(organization_id=7, event_id=3)
    assert out is None
    assert session.execute.await_count == 1


async def test_mindbot_usage_repository_thread_calls_execute() -> None:
    session = AsyncMock()
    fake_scalar = MagicMock()
    fake_scalar.all.return_value = []
    fake_result = MagicMock()
    fake_result.scalars.return_value = fake_scalar
    session.execute = AsyncMock(return_value=fake_result)

    repo = MindbotUsageRepository(session)
    out = await repo.list_events_for_thread(
        organization_id=7,
        dingtalk_staff_id="s1",
        dingtalk_conversation_id="c1",
        dify_conversation_id=None,
        limit=10,
        before_id=100,
    )
    assert out == []
    assert session.execute.await_count == 1


async def test_mindbot_usage_repository_list_calls_execute() -> None:
    session = AsyncMock()
    fake_scalar = MagicMock()
    fake_scalar.all.return_value = []
    fake_result = MagicMock()
    fake_result.scalars.return_value = fake_scalar
    session.execute = AsyncMock(return_value=fake_result)

    repo = MindbotUsageRepository(session)
    out = await repo.list_events_for_org(
        organization_id=7,
        limit=10,
        before_id=100,
        dingtalk_staff_id="s1",
    )
    assert out == []
    assert session.execute.await_count == 1
