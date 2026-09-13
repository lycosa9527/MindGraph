"""教研组 join cascades onto 课例 membership."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi import HTTPException

from models.domain.workshop_chat import ChatChannel
from routers.features.workshop_chat.dependencies import require_membership
from services.features.workshop_chat.group_lesson_membership import (
    add_missing_memberships,
    backfill_joined_group_lessons,
    ensure_lesson_membership_if_group_member,
    is_teaching_group,
    join_channel_with_lessons,
    subscribe_group_members_to_lesson,
    subscribe_user_to_group_lessons,
)
from tests.typing_helpers import as_type


def _channel(
    channel_id: int,
    *,
    parent_id: int | None = None,
    channel_type: str = "public",
) -> ChatChannel:
    """Minimal channel row."""
    return as_type(
        SimpleNamespace(
            id=channel_id,
            parent_id=parent_id,
            channel_type=channel_type,
            is_archived=False,
        ),
        ChatChannel,
    )


def _id_rows(ids: list[int]) -> MagicMock:
    """Result whose ``.all()`` yields ``(id,)`` tuples."""
    result = MagicMock()
    result.all.return_value = [(row_id,) for row_id in ids]
    return result


def test_is_teaching_group_excludes_announce_and_lessons() -> None:
    """Only top-level non-announce channels are 教研组."""
    assert is_teaching_group(_channel(1)) is True
    assert is_teaching_group(_channel(2, channel_type="announce")) is False
    assert is_teaching_group(_channel(3, parent_id=1)) is False


@pytest.mark.asyncio
async def test_add_missing_memberships_skips_existing() -> None:
    """Already-subscribed channels are not inserted again."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_id_rows([10]))
    db.add = MagicMock()

    added = await add_missing_memberships(db, user_id=286, channel_ids=[10, 11])

    assert added == 1
    assert db.add.call_count == 1
    assert db.add.call_args.args[0].channel_id == 11
    assert db.add.call_args.args[0].user_id == 286


@pytest.mark.asyncio
async def test_subscribe_user_to_group_lessons_adds_live_children() -> None:
    """Join-group helper inserts a row per live 课例."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_id_rows([118, 120]), _id_rows([])])
    db.add = MagicMock()

    added = await subscribe_user_to_group_lessons(db, group_id=117, user_id=286)

    assert added == 2
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_subscribe_group_members_to_lesson_skips_owner() -> None:
    """New 课例 copies group members except the owner already inserted."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_id_rows([3, 286]), _id_rows([3])])
    db.add = MagicMock()

    added = await subscribe_group_members_to_lesson(
        db,
        group_id=117,
        lesson_id=121,
        skip_user_ids={3},
    )

    assert added == 1
    assert db.add.call_args.args[0].user_id == 286
    assert db.add.call_args.args[0].channel_id == 121


@pytest.mark.asyncio
async def test_backfill_joined_group_lessons_only_for_joined_groups() -> None:
    """A teacher who already joined 思维训练线上培训 gets missing 课例 rows."""
    group = _channel(117)
    other = _channel(200)
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _id_rows([117]),
            _id_rows([118, 120]),
            _id_rows([]),
        ]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()

    added = await backfill_joined_group_lessons(db, user_id=286, channels=[group, other])

    assert added == 2
    db.commit.assert_awaited()
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_ensure_lesson_membership_inherits_from_group() -> None:
    """Opening a 课例 while in the 教研组 inserts the child membership."""
    lesson = _channel(120, parent_id=117)
    lesson_result = MagicMock()
    lesson_result.scalar_one_or_none.return_value = lesson
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _id_rows([]),
            lesson_result,
            _id_rows([117]),
            _id_rows([]),
        ]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()

    ok = await ensure_lesson_membership_if_group_member(db, channel_id=120, user_id=286)

    assert ok is True
    db.commit.assert_awaited()
    assert db.add.call_args.args[0].channel_id == 120


@pytest.mark.asyncio
async def test_ensure_lesson_membership_rejects_outsider() -> None:
    """No 教研组 row means the 课例 stays closed."""
    lesson = _channel(120, parent_id=117)
    lesson_result = MagicMock()
    lesson_result.scalar_one_or_none.return_value = lesson
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _id_rows([]),
            lesson_result,
            _id_rows([]),
        ]
    )
    db.add = MagicMock()

    ok = await ensure_lesson_membership_if_group_member(db, channel_id=120, user_id=286)

    assert ok is False
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_require_membership_uses_group_inherit() -> None:
    """POST /topics no longer 403s when the teacher is in the parent 教研组."""
    lesson = _channel(120, parent_id=117)
    lesson_result = MagicMock()
    lesson_result.scalar_one_or_none.return_value = lesson
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _id_rows([]),
            lesson_result,
            _id_rows([117]),
            _id_rows([]),
        ]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()

    await require_membership(db, channel_id=120, user_id=286)

    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_require_membership_still_403_without_group() -> None:
    """Teachers outside the 教研组 still need to join."""
    lesson = _channel(120, parent_id=117)
    lesson_result = MagicMock()
    lesson_result.scalar_one_or_none.return_value = lesson
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _id_rows([]),
            lesson_result,
            _id_rows([]),
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_membership(db, channel_id=120, user_id=286)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "You must join this channel first"


@pytest.mark.asyncio
async def test_join_group_cascades_to_lessons() -> None:
    """POST /join on a 教研组 also inserts 课例 memberships."""
    group = _channel(117)
    group_result = MagicMock()
    group_result.scalar_one_or_none.return_value = group
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            group_result,
            _id_rows([]),
            _id_rows([118, 120, 121]),
            _id_rows([]),
        ]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()

    ok = await join_channel_with_lessons(db, 117, 286)

    assert ok is True
    assert db.add.call_count == 4
    db.commit.assert_awaited()
    added_ids = {call.args[0].channel_id for call in db.add.call_args_list}
    assert added_ids == {117, 118, 120, 121}


@pytest.mark.asyncio
async def test_join_already_in_group_still_fills_lessons() -> None:
    """A second join (or already-member) still backfills 课例 rows."""
    group = _channel(117)
    group_result = MagicMock()
    group_result.scalar_one_or_none.return_value = group
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            group_result,
            _id_rows([117]),
            _id_rows([120]),
            _id_rows([]),
        ]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()

    ok = await join_channel_with_lessons(db, 117, 286)

    assert ok is True
    assert db.add.call_count == 1
    assert db.add.call_args.args[0].channel_id == 120
    db.commit.assert_awaited()
