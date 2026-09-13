"""研习社 send_message rejects a topic or parent from another channel."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.features.workshop_chat.message_service import (
    MessageNarrowError,
    MessageService,
)


def _scalar_result(value: object) -> MagicMock:
    """Result whose ``scalar_one_or_none`` returns *value*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_send_rejects_topic_from_other_channel() -> None:
    """A topic_id that belongs to another channel is a 404-class error."""
    sender = SimpleNamespace(id=7, name="Ada")
    channel = SimpleNamespace(id=10, organization_id=3)
    foreign_topic = SimpleNamespace(id=44, channel_id=99)
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(sender),
            _scalar_result(channel),
            _scalar_result(foreign_topic),
        ]
    )

    with pytest.raises(MessageNarrowError, match="Topic not found"):
        await MessageService.send_message(
            db,
            10,
            7,
            "hello",
            topic_id=44,
        )


@pytest.mark.asyncio
async def test_send_rejects_parent_from_other_channel() -> None:
    """A reply parent must live in the same channel and topic."""
    sender = SimpleNamespace(id=7, name="Ada")
    channel = SimpleNamespace(id=10, organization_id=3)
    parent = SimpleNamespace(id=8, channel_id=11, topic_id=None)
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalar_result(sender),
            _scalar_result(channel),
            _scalar_result(parent),
        ]
    )

    with pytest.raises(MessageNarrowError, match="Parent message"):
        await MessageService.send_message(
            db,
            10,
            7,
            "reply",
            parent_id=8,
        )
