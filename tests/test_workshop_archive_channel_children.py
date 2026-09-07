"""Archiving a teaching group must also archive its live lesson studies."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.features.workshop_chat.channel_service import ChannelService


def _channel(channel_id: int, parent_id: int | None) -> SimpleNamespace:
    """Minimal channel row for archive tests."""
    return SimpleNamespace(
        id=channel_id,
        parent_id=parent_id,
        is_archived=False,
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_archive_group_archives_live_children() -> None:
    """A top-level 教研组 archive also archives live 课例 under it."""
    parent = _channel(10, None)
    child_a = _channel(11, 10)
    child_b = _channel(12, 10)
    parent_result = MagicMock()
    parent_result.scalar_one_or_none.return_value = parent
    children_result = MagicMock()
    children_result.scalars.return_value.all.return_value = [child_a, child_b]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[parent_result, children_result])
    db.commit = AsyncMock()

    ok = await ChannelService.archive_channel(db, 10)

    assert ok is True
    assert parent.is_archived is True
    assert child_a.is_archived is True
    assert child_b.is_archived is True
    assert db.execute.await_count == 2
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_archive_lesson_does_not_walk_children() -> None:
    """Archiving a 课例 only touches that row."""
    lesson = _channel(22, 10)
    result = MagicMock()
    result.scalar_one_or_none.return_value = lesson
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    ok = await ChannelService.archive_channel(db, 22)

    assert ok is True
    assert lesson.is_archived is True
    assert db.execute.await_count == 1
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_archive_missing_channel_returns_false() -> None:
    """Unknown id is a no-op."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    ok = await ChannelService.archive_channel(db, 99)

    assert ok is False
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_group_deletes_children() -> None:
    """A top-level 教研组 delete also deletes 课例 rows."""
    parent = _channel(10, None)
    child_a = _channel(11, 10)
    child_b = _channel(12, 10)
    parent_result = MagicMock()
    parent_result.scalar_one_or_none.return_value = parent
    children_result = MagicMock()
    children_result.scalars.return_value.all.return_value = [child_a, child_b]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[parent_result, children_result, MagicMock()])
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    ok = await ChannelService.delete_channel(db, 10)

    assert ok is True
    deleted_ids = [call.args[0].id for call in db.delete.await_args_list]
    assert deleted_ids == [11, 12, 10]
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_lesson_only_deletes_that_row() -> None:
    """Deleting a 课例 does not walk siblings."""
    lesson = _channel(22, 10)
    result = MagicMock()
    result.scalar_one_or_none.return_value = lesson
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[result, MagicMock()])
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    ok = await ChannelService.delete_channel(db, 22)

    assert ok is True
    assert db.delete.await_count == 1
    assert db.delete.await_args.args[0] is lesson
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_missing_channel_returns_false() -> None:
    """Unknown id is a no-op."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    ok = await ChannelService.delete_channel(db, 99)

    assert ok is False
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()
