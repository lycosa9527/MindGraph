"""Group highlights persist on the server and are visible to every participant."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from models.domain.mindmate_seminar import MindmateSeminarHighlight
from services.features.mindmate_seminar.highlights import (
    SeminarHighlightDraft,
    create_seminar_highlight,
    highlight_payload,
    parse_highlight_instant,
    user_may_delete_highlight,
)


def _session() -> MagicMock:
    session = MagicMock()
    session.id = "sess-highlights"
    session.code = "ABC-DEF"
    session.owner_user_id = 7
    return session


def _user(user_id: int = 4, name: str = "Ada") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.name = name
    return user


def _rls(db: MagicMock) -> object:
    class _Box:
        async def __aenter__(self) -> MagicMock:
            return db

        async def __aexit__(self, *_args: object) -> bool:
            return False

    return _Box()


def test_parse_highlight_instant_accepts_zulu() -> None:
    """Zulu timestamps from the seminar client become aware datetimes."""
    parsed = parse_highlight_instant("2026-11-11T21:34:00Z")
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_highlight_payload_exposes_creator() -> None:
    """Everyone in the room needs the creator id, not only the excerpt text."""
    created = datetime(2026, 11, 11, 13, 34, tzinfo=UTC)
    row = MindmateSeminarHighlight(
        id=str(uuid4()),
        session_id="sess-highlights",
        created_by_user_id=4,
        created_by_name="Ada",
        author_name="MindMate",
        text="Keep this",
        message_id=18,
        message_at=created,
        created_at=created,
    )
    payload = highlight_payload(row)
    assert payload["created_by_user_id"] == 4
    assert payload["author_name"] == "MindMate"
    assert payload["message_id"] == 18


@pytest.mark.asyncio
async def test_creator_and_leader_may_delete() -> None:
    """A pin can be removed by its author or by the seminar leader."""
    session = _session()
    with patch(
        "services.features.mindmate_seminar.highlights.list_group_member_roles",
        AsyncMock(return_value={7: "leader", 4: "researcher"}),
    ):
        assert await user_may_delete_highlight(session, 4, 4)
        assert await user_may_delete_highlight(session, 7, 4)
        assert not await user_may_delete_highlight(session, 9, 4)


@pytest.mark.asyncio
async def test_create_seminar_highlight_broadcasts_to_the_room() -> None:
    """A new pin is stored and pushed so other browsers see it immediately."""
    session = _session()
    db = MagicMock()
    db.scalar = AsyncMock(return_value=0)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    with (
        patch(
            "services.features.mindmate_seminar.highlights.user_observes_seminar",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.features.mindmate_seminar.highlights.system_rls_session",
            return_value=_rls(db),
        ),
        patch(
            "services.features.mindmate_seminar.highlights.broadcast_to_all",
            AsyncMock(),
        ) as broadcast,
    ):
        payload = await create_seminar_highlight(
            session,
            _user(),
            SeminarHighlightDraft(
                text="Keep this line",
                author_name="MindMate",
                created_by_name="Ada",
                message_id=18,
                message_at=datetime(2026, 11, 11, tzinfo=UTC),
            ),
        )
    assert payload["text"] == "Keep this line"
    assert payload["created_by_user_id"] == 4
    broadcast.assert_awaited_once()
    called = broadcast.await_args
    assert called is not None
    frame = called.args[1]
    assert frame["type"] == "seminar_highlight"
    assert frame["action"] == "set"
    assert frame["highlight"]["text"] == "Keep this line"


@pytest.mark.asyncio
async def test_observers_cannot_pin_highlights() -> None:
    """观摩学习 may read highlights, not create them."""
    with patch(
        "services.features.mindmate_seminar.highlights.user_observes_seminar",
        AsyncMock(return_value=True),
    ):
        with pytest.raises(ValueError, match="observer_readonly"):
            await create_seminar_highlight(
                _session(),
                _user(),
                SeminarHighlightDraft(
                    text="Nope",
                    author_name="Ada",
                    created_by_name="Ada",
                    message_id=1,
                    message_at=None,
                ),
            )
