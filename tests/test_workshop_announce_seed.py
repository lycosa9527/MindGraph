"""Announce-channel seed must tolerate duplicate rows from a worker race."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from models.domain.workshop_chat import ChatChannel
from services.features.workshop_chat.default_channels import (
    archive_duplicate_named_channels,
    archive_retired_seed_channels,
    canonical_announce_channel,
    ensure_default_stream_memberships,
    seed_announce_channel,
)
from services.features.workshop_chat.seed_channel_data import (
    KEEPER_GROUP_NAME,
    KEEPER_LESSON_NAME,
)


def _channel(channel_id: int, *, archived: bool = False) -> ChatChannel:
    """Build an in-memory announce channel for picker tests."""
    return ChatChannel(
        id=channel_id,
        name="系统公告",
        created_by=1,
        channel_type="announce",
        is_archived=archived,
    )


def test_canonical_prefers_oldest_live_over_archived() -> None:
    """A newer live row wins over an older archived duplicate."""
    archived = _channel(1, archived=True)
    live_older = _channel(2)
    live_newer = _channel(3)
    picked = canonical_announce_channel([archived, live_older, live_newer])
    assert picked is live_older


def test_canonical_restores_oldest_when_all_archived() -> None:
    """If every announce row is archived, keep the first-created one."""
    first = _channel(4, archived=True)
    second = _channel(9, archived=True)
    assert canonical_announce_channel([first, second]) is first


def test_canonical_empty_list() -> None:
    """No announce rows means the seeder should create one."""
    assert canonical_announce_channel([]) is None


@pytest.mark.asyncio
async def test_seed_announce_does_not_crash_on_duplicate_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two announce rows must not raise MultipleResultsFound."""
    keeper = _channel(11)
    extra = _channel(12)

    async def fake_list(_db: object) -> list[ChatChannel]:
        return [keeper, extra]

    monkeypatch.setattr(
        "services.features.workshop_chat.default_channels._list_announce_channels",
        fake_list,
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    topic_count = MagicMock()
    topic_count.scalar.return_value = 99
    membership = MagicMock()
    membership.scalar_one_or_none.return_value = SimpleNamespace(id=1)
    empty_topics = MagicMock()
    empty_topics.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[topic_count, empty_topics, membership])

    result = await seed_announce_channel(db, created_by=3)

    assert result == {"id": 11, "name": "系统公告", "channel_type": "announce"}
    assert extra.is_archived is True
    assert keeper.is_archived is False
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_announce_retries_after_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A unique-index race reuses the winning announce row."""
    winner = _channel(21)
    resolve_calls = [0]

    async def fake_resolve(_db: object) -> ChatChannel | None:
        if resolve_calls[0] == 0:
            resolve_calls[0] += 1
            return None
        return winner

    async def fake_create(_db: object, _user_id: int, _base: object) -> None:
        return None

    monkeypatch.setattr(
        "services.features.workshop_chat.default_channels._resolve_announce_channel",
        fake_resolve,
    )
    monkeypatch.setattr(
        "services.features.workshop_chat.default_channels._create_announce_channel",
        fake_create,
    )
    monkeypatch.setattr(
        "services.features.workshop_chat.default_channels._top_up_existing_announce",
        AsyncMock(),
    )

    result = await seed_announce_channel(AsyncMock(), created_by=3)
    assert result == {"id": 21, "name": "系统公告", "channel_type": "announce"}


@pytest.mark.asyncio
async def test_create_announce_swallows_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flush unique violation rolls back and then reuses the winner."""
    winner = _channel(21)
    resolve_calls = [0]

    async def fake_resolve(_db: object) -> ChatChannel | None:
        if resolve_calls[0] == 0:
            resolve_calls[0] += 1
            return None
        return winner

    monkeypatch.setattr(
        "services.features.workshop_chat.default_channels._resolve_announce_channel",
        fake_resolve,
    )
    monkeypatch.setattr(
        "services.features.workshop_chat.default_channels._top_up_existing_announce",
        AsyncMock(),
    )

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock(
        side_effect=IntegrityError("dup", {}, Exception("dup")),
    )
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    result = await seed_announce_channel(db, created_by=3)
    assert result == {"id": 21, "name": "系统公告", "channel_type": "announce"}
    db.rollback.assert_awaited()


def _org_channel(
    channel_id: int,
    name: str,
    *,
    parent_id: int | None = None,
) -> SimpleNamespace:
    """Minimal channel row for retired-seed archive tests."""
    return SimpleNamespace(
        id=channel_id,
        name=name,
        parent_id=parent_id,
        is_archived=False,
    )


@pytest.mark.asyncio
async def test_archive_retired_seed_keeps_announce_and_beiying() -> None:
    """Retired demo groups/lessons archive; keeper 语文 / 背影 stay live."""
    stem = _org_channel(1, "STEM教研组")
    stem_lesson = _org_channel(2, "《杠杆的科学》", parent_id=1)
    yuwen = _org_channel(3, KEEPER_GROUP_NAME)
    beiying = _org_channel(4, KEEPER_LESSON_NAME, parent_id=3)
    kong = _org_channel(5, "《孔乙己》（鲁迅）", parent_id=3)
    announce = _org_channel(6, "系统公告")

    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [
        stem,
        stem_lesson,
        yuwen,
        beiying,
        kong,
        announce,
    ]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=listed)
    db.commit = AsyncMock()

    archived = await archive_retired_seed_channels(db, organization_id=5)

    assert archived == 3
    assert stem.is_archived is True
    assert stem_lesson.is_archived is True
    assert kong.is_archived is True
    assert yuwen.is_archived is False
    assert beiying.is_archived is False
    assert announce.is_archived is False
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_archive_retired_seed_archives_math_group() -> None:
    """数理化教研组 and its canned lessons are retired by name."""
    math_group = _org_channel(10, "数理化教研组")
    gougu = _org_channel(11, "《勾股定理》", parent_id=10)
    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [math_group, gougu]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=listed)
    db.commit = AsyncMock()

    archived = await archive_retired_seed_channels(db, organization_id=5)

    assert archived == 2
    assert math_group.is_archived is True
    assert gougu.is_archived is True


@pytest.mark.asyncio
async def test_archive_retired_archives_duplicate_yuwen_and_its_children() -> None:
    """A second 语文教研组 forest is retired; oldest keeper + 背影 stay."""
    yuwen = _org_channel(3, KEEPER_GROUP_NAME)
    beiying = _org_channel(4, KEEPER_LESSON_NAME, parent_id=3)
    yuwen_copy = _org_channel(27, KEEPER_GROUP_NAME)
    beiying_copy = _org_channel(28, KEEPER_LESSON_NAME, parent_id=27)
    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [
        yuwen,
        beiying,
        yuwen_copy,
        beiying_copy,
    ]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=listed)
    db.commit = AsyncMock()

    archived = await archive_retired_seed_channels(db, organization_id=5)

    assert archived == 2
    assert yuwen.is_archived is False
    assert beiying.is_archived is False
    assert yuwen_copy.is_archived is True
    assert beiying_copy.is_archived is True


@pytest.mark.asyncio
async def test_archive_duplicate_named_keeps_oldest() -> None:
    """Same-name live groups collapse to the lowest id."""
    first = _org_channel(14, KEEPER_GROUP_NAME)
    second = _org_channel(27, KEEPER_GROUP_NAME)
    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [first, second]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=listed)
    db.commit = AsyncMock()

    archived = await archive_duplicate_named_channels(db, organization_id=5)

    assert archived == 1
    assert first.is_archived is False
    assert second.is_archived is True
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ensure_default_streams_joins_keeper_group_and_lesson() -> None:
    """Later org members subscribe to 语文教研组 and 《背影》."""
    yuwen = _org_channel(3, KEEPER_GROUP_NAME)
    beiying = _org_channel(4, KEEPER_LESSON_NAME, parent_id=3)
    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [yuwen, beiying]
    missing = MagicMock()
    missing.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[listed, missing, missing])
    db.commit = AsyncMock()
    db.add = MagicMock()

    added = await ensure_default_stream_memberships(db, organization_id=5, user_id=42)

    assert added == 2
    assert db.add.call_count == 2
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ensure_default_streams_skips_existing_membership() -> None:
    """Already-joined users do not get a second member row."""
    yuwen = _org_channel(3, KEEPER_GROUP_NAME)
    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [yuwen]
    present = MagicMock()
    present.scalar_one_or_none.return_value = 99
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[listed, present])
    db.commit = AsyncMock()
    db.add = MagicMock()

    added = await ensure_default_stream_memberships(db, organization_id=5, user_id=42)

    assert added == 0
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
