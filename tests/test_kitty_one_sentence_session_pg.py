"""Tests for one-sentence session registry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from services.kitty.session.one_sentence_session_pg import (
    ensure_one_sentence_session,
    serialize_session_row,
)

_EPHEMERAL_SCOPE = "66e3619a-48f4-4c0d-b7f4-928564f87f32"


def test_serialize_session_row_includes_session_id() -> None:
    """Serialized session exposes stable session_id for analytics joins."""
    row = MagicMock()
    row.id = "11111111-2222-4333-8444-555555555555"
    row.user_id = 9
    row.organization_id = 2
    row.diagram_scope = "scope-uuid"
    row.diagram_id = None
    row.diagram_type = "mindmap"
    row.status = "active"
    row.turn_count = 4
    row.create_turn_count = 2
    row.edit_turn_count = 2
    row.first_prompt_preview = "北京三日游"
    row.last_voice_session_id = "voice_abc"
    row.created_at = None
    row.updated_at = None
    row.last_activity_at = None
    payload = serialize_session_row(row)
    assert payload["session_id"] == row.id
    assert payload["diagram_scope"] == "scope-uuid"


def _session_ctx(session: AsyncMock) -> AsyncMock:
    session_ctx = AsyncMock()

    async def _enter_session(*_args: object, **_kwargs: object) -> AsyncMock:
        return session

    session_ctx.__aenter__.side_effect = _enter_session
    session_ctx.__aexit__.return_value = False
    return session_ctx


@pytest.mark.asyncio
async def test_ensure_one_sentence_session_returns_existing() -> None:
    """Second call for same user+scope reuses session id."""
    existing = MagicMock()
    existing.id = "existing-session"
    existing.diagram_type = "mindmap"
    existing.diagram_id = None

    session = AsyncMock()
    session.commit = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    with patch(
        "services.kitty.session.one_sentence_session_pg.system_rls_session",
        return_value=_session_ctx(session),
    ):
        with patch("services.kitty.session.one_sentence_session_pg.KittyOneSentenceSessionRepository") as repo_cls:
            repo_cls.return_value.get_by_user_scope = AsyncMock(return_value=existing)
            session_id = await ensure_one_sentence_session(
                user_id=5,
                organization_id=1,
                diagram_scope="diagram-scope",
            )
    assert session_id == "existing-session"


@pytest.mark.asyncio
async def test_ensure_one_sentence_session_skips_fk_for_unsaved_uuid_scope() -> None:
    """UUID-shaped Kitty scopes must not set diagram_id before the diagram row exists."""
    session = AsyncMock()
    session.commit = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    with patch(
        "services.kitty.session.one_sentence_session_pg.system_rls_session",
        return_value=_session_ctx(session),
    ):
        with patch("services.kitty.session.one_sentence_session_pg.KittyOneSentenceSessionRepository") as repo_cls:
            repo = repo_cls.return_value
            repo.get_by_user_scope = AsyncMock(return_value=None)
            repo.insert = AsyncMock()
            session_id = await ensure_one_sentence_session(
                user_id=5,
                organization_id=1,
                diagram_scope=_EPHEMERAL_SCOPE,
                diagram_type="mindmap",
            )

    assert session_id is not None
    assert repo.insert.await_args is not None
    inserted = repo.insert.await_args.args[0]
    assert inserted.diagram_scope == _EPHEMERAL_SCOPE
    assert inserted.diagram_id is None


@pytest.mark.asyncio
async def test_ensure_one_sentence_session_links_saved_diagram() -> None:
    """When the library diagram exists, diagram_id is set for analytics joins."""
    session = AsyncMock()
    session.commit = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _EPHEMERAL_SCOPE
    session.execute = AsyncMock(return_value=result)

    with patch(
        "services.kitty.session.one_sentence_session_pg.system_rls_session",
        return_value=_session_ctx(session),
    ):
        with patch("services.kitty.session.one_sentence_session_pg.KittyOneSentenceSessionRepository") as repo_cls:
            repo = repo_cls.return_value
            repo.get_by_user_scope = AsyncMock(return_value=None)
            repo.insert = AsyncMock()
            session_id = await ensure_one_sentence_session(
                user_id=5,
                organization_id=1,
                diagram_scope=_EPHEMERAL_SCOPE,
            )

    assert session_id is not None
    assert repo.insert.await_args is not None
    inserted = repo.insert.await_args.args[0]
    assert inserted.diagram_id == _EPHEMERAL_SCOPE


@pytest.mark.asyncio
async def test_ensure_one_sentence_session_recovers_from_unique_violation() -> None:
    """Concurrent creators reuse the winner row after IntegrityError."""
    raced = MagicMock()
    raced.id = "winner-session"

    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    with patch(
        "services.kitty.session.one_sentence_session_pg.system_rls_session",
        return_value=_session_ctx(session),
    ):
        with patch("services.kitty.session.one_sentence_session_pg.KittyOneSentenceSessionRepository") as repo_cls:
            repo = repo_cls.return_value
            repo.get_by_user_scope = AsyncMock(side_effect=[None, raced])
            repo.insert = AsyncMock(side_effect=IntegrityError("dup", {}, Exception("dup")))
            session_id = await ensure_one_sentence_session(
                user_id=5,
                organization_id=1,
                diagram_scope="diagram-scope",
            )
    assert session_id == "winner-session"
    session.rollback.assert_awaited_once()
