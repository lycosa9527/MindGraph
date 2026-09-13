"""研习社 unread: topic read must not wipe sibling topic badges."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.features.workshop_chat.channel_unread import merge_unread_parts
from services.features.workshop_chat.topic_service import TopicService


def test_merge_unread_parts_sums_main_stream_and_topics() -> None:
    """Channel badge is main-stream plus still-unread topics."""
    merged = merge_unread_parts(
        [10, 11],
        {10: 2},
        {10: 3},
        {10: 1, 11: 4},
    )
    assert merged[10] == 6
    assert merged[11] == 4


@pytest.mark.asyncio
async def test_mark_topic_read_does_not_clear_sibling_topic_unread() -> None:
    """Opening topic A must not advance ChannelMember.last_read_message_id."""
    topic = SimpleNamespace(id=2, channel_id=5)
    topic_result = MagicMock()
    topic_result.scalar_one_or_none.return_value = topic
    pref_result = MagicMock()
    pref_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[topic_result, pref_result])
    db.add = MagicMock()

    result = await TopicService.mark_topic_read(db, 2, 99)

    assert result == {"topic_id": 2, "marked_read": True}
    assert db.execute.await_count == 2
    assert db.add.call_count == 1
    pref = db.add.call_args.args[0]
    assert pref.user_id == 99
    assert pref.topic_id == 2
    assert pref.last_updated is not None
    db.commit.assert_awaited_once()
