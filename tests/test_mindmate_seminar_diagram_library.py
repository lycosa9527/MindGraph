"""Copy a MindMate seminar diagram preview into the viewer's library."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram.generation_library_save import SAVE_LIMIT_REACHED
from services.features.mindmate_seminar.diagram_library import (
    COPY_FORBIDDEN,
    COPY_LIMIT,
    COPY_NOT_FOUND,
    actor_may_copy_collab_diagram,
    load_shared_canvas_diagram_preview,
    normalize_collab_preview_id,
    save_collab_diagram_for_user,
)


def test_normalize_collab_preview_id() -> None:
    """Only an 8-hex temp PNG id is accepted."""
    assert normalize_collab_preview_id("DeadBeef") == "deadbeef"
    assert normalize_collab_preview_id("short") is None
    assert normalize_collab_preview_id("dead_beef") is None


def test_owner_can_copy_after_the_seminar_ends() -> None:
    """The host can still save a diagram from a finished transcript."""
    assert actor_may_copy_collab_diagram(
        owner_user_id=7,
        actor_user_id=7,
        session_ended=True,
        is_live_participant=False,
    )


def test_guest_can_copy_only_while_in_the_live_room() -> None:
    """A participant who has left, or a finished room, does not get a copy."""
    assert actor_may_copy_collab_diagram(
        owner_user_id=7,
        actor_user_id=8,
        session_ended=False,
        is_live_participant=True,
    )
    assert not actor_may_copy_collab_diagram(
        owner_user_id=7,
        actor_user_id=8,
        session_ended=False,
        is_live_participant=False,
    )
    assert not actor_may_copy_collab_diagram(
        owner_user_id=7,
        actor_user_id=8,
        session_ended=True,
        is_live_participant=True,
    )


def _user(user_id: int = 8) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.organization_id = 3
    return user


@pytest.mark.asyncio
async def test_save_returns_existing_personal_copy() -> None:
    """A second click reuses the diagram already stored for this user."""
    with (
        patch(
            "services.features.mindmate_seminar.diagram_library._load_session_access",
            new=AsyncMock(return_value=("ABC-DEF", 7, False)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._session_has_preview",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.get_mindmate_seminar_manager",
        ) as manager_factory,
        patch(
            "services.features.mindmate_seminar.diagram_library._find_user_copy",
            new=AsyncMock(return_value=("diagram-1", True)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._insert_preview_copy",
            new=AsyncMock(),
        ) as insert_copy,
    ):
        manager_factory.return_value.is_participant = AsyncMock(return_value=True)
        diagram_id, error = await save_collab_diagram_for_user("session-1", "deadbeef", _user())
    assert error == ""
    assert diagram_id == "diagram-1"
    insert_copy.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_inserts_a_copy_for_a_live_participant() -> None:
    """The first click stores the preview spec in that participant's library."""
    with (
        patch(
            "services.features.mindmate_seminar.diagram_library._load_session_access",
            new=AsyncMock(return_value=("ABC-DEF", 7, False)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._session_has_preview",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.get_mindmate_seminar_manager",
        ) as manager_factory,
        patch(
            "services.features.mindmate_seminar.diagram_library._find_user_copy",
            new=AsyncMock(return_value=(None, True)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._insert_preview_copy",
            new=AsyncMock(return_value=("diagram-2", "")),
        ) as insert_copy,
    ):
        manager_factory.return_value.is_participant = AsyncMock(return_value=True)
        diagram_id, error = await save_collab_diagram_for_user("session-1", "deadbeef", _user())
    assert error == ""
    assert diagram_id == "diagram-2"
    insert_copy.assert_awaited()


@pytest.mark.asyncio
async def test_save_rejects_a_guest_after_the_room_ends() -> None:
    """Only the host can copy a diagram once the seminar has ended."""
    with (
        patch(
            "services.features.mindmate_seminar.diagram_library._load_session_access",
            new=AsyncMock(return_value=("ABC-DEF", 7, True)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._session_has_preview",
            new=AsyncMock(return_value=True),
        ),
    ):
        diagram_id, error = await save_collab_diagram_for_user("session-1", "deadbeef", _user())
    assert diagram_id is None
    assert error == COPY_FORBIDDEN


@pytest.mark.asyncio
async def test_save_hides_a_preview_that_is_not_in_the_seminar() -> None:
    """A preview id from another conversation is treated as missing."""
    with (
        patch(
            "services.features.mindmate_seminar.diagram_library._load_session_access",
            new=AsyncMock(return_value=("ABC-DEF", 7, False)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._session_has_preview",
            new=AsyncMock(return_value=False),
        ),
    ):
        diagram_id, error = await save_collab_diagram_for_user("session-1", "deadbeef", _user(7))
    assert diagram_id is None
    assert error == COPY_NOT_FOUND


@pytest.mark.asyncio
async def test_save_reports_a_full_library() -> None:
    """A full library is reported without writing a diagram id onto the shared preview."""
    with (
        patch(
            "services.features.mindmate_seminar.diagram_library._load_session_access",
            new=AsyncMock(return_value=("ABC-DEF", 7, False)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library._session_has_preview",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.get_mindmate_seminar_manager",
        ) as manager_factory,
        patch(
            "services.features.mindmate_seminar.diagram_library._find_user_copy",
            new=AsyncMock(return_value=(None, True)),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.get_generation_preview_outcome",
            new=AsyncMock(
                return_value={
                    "spec": {"topic": "水循环"},
                    "diagram_type": "mind_map",
                    "title": "水循环",
                    "language": "zh",
                }
            ),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.try_save_diagram_to_library",
            new=AsyncMock(return_value=SAVE_LIMIT_REACHED),
        ) as save_diagram,
    ):
        manager_factory.return_value.is_participant = AsyncMock(return_value=True)
        diagram_id, error = await save_collab_diagram_for_user("session-1", "deadbeef", _user())
    assert diagram_id is None
    assert error == COPY_LIMIT
    save_diagram.assert_awaited()


class _OwnerResult:
    """Stand-in for a SQLAlchemy result that yields one user id."""

    def __init__(self, owner: int) -> None:
        self._owner = owner

    def scalar_one_or_none(self) -> int:
        """Return the diagram owner."""
        return self._owner


class _OwnerDb:
    """Stand-in for the system session used to read diagrams.user_id."""

    def __init__(self, owner: int) -> None:
        self._owner = owner

    async def execute(self, _stmt: object) -> _OwnerResult:
        """Return the canned owner row."""
        return _OwnerResult(self._owner)


class _OwnerSession:
    """Async context manager around ``_OwnerDb``."""

    def __init__(self, owner: int) -> None:
        self._owner = owner

    async def __aenter__(self) -> _OwnerDb:
        return _OwnerDb(self._owner)

    async def __aexit__(self, *_args: object) -> bool:
        return False


_ASKER_DIAGRAM = "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_viewer_opens_diagram_saved_for_the_asker() -> None:
    """A MindGraph reply has no chat sender; other people still open the asker's copy."""
    session = MagicMock()
    session.id = "session-1"
    cache = MagicMock()

    async def _get(user_id: int, _diagram_id: str):
        if user_id == 42:
            return {
                "spec": {"topic": "小儿童"},
                "diagram_type": "double_bubble_map",
                "title": "对比",
                "language": "zh",
            }
        return None

    cache.get_diagram = AsyncMock(side_effect=_get)
    manager = MagicMock()
    manager.load_session_by_id_any = AsyncMock(return_value=session)
    with (
        patch(
            "services.features.mindmate_seminar.diagram_library.get_mindmate_seminar_manager",
            return_value=manager,
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.session_contains_canvas_diagram",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.user_may_open_shared_canvas",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.canvas_share_sender_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.system_rls_session",
            return_value=_OwnerSession(42),
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.get_diagram_cache",
            return_value=cache,
        ),
        patch(
            "services.features.mindmate_seminar.diagram_library.coerce_prompt_to_diagram_spec",
            side_effect=lambda spec, _diagram_type: spec,
        ),
    ):
        payload, error = await load_shared_canvas_diagram_preview("session-1", _ASKER_DIAGRAM, _user(8))
    assert error == ""
    assert payload is not None
    assert payload["diagram_id"] == _ASKER_DIAGRAM
    assert cache.get_diagram.await_args_list[0].args == (8, _ASKER_DIAGRAM)
    assert cache.get_diagram.await_args_list[1].args == (42, _ASKER_DIAGRAM)
