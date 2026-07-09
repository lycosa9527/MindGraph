"""Tests for one-sentence session registry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.one_sentence_session_pg import (
    ensure_one_sentence_session,
    serialize_session_row,
)


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


@pytest.mark.asyncio
async def test_ensure_one_sentence_session_returns_existing() -> None:
    """Second call for same user+scope reuses session id."""
    existing = MagicMock()
    existing.id = "existing-session"
    existing.diagram_type = "mindmap"

    session = AsyncMock()
    session.commit = AsyncMock()

    session_ctx = AsyncMock()

    async def _enter_session(*_args: object, **_kwargs: object) -> AsyncMock:
        return session

    session_ctx.__aenter__.side_effect = _enter_session
    session_ctx.__aexit__.return_value = False

    with patch("services.kitty.session.one_sentence_session_pg.system_rls_session", return_value=session_ctx):
        with patch("services.kitty.session.one_sentence_session_pg.KittyOneSentenceSessionRepository") as repo_cls:
            repo_cls.return_value.get_by_user_scope = AsyncMock(return_value=existing)
            session_id = await ensure_one_sentence_session(
                user_id=5,
                organization_id=1,
                diagram_scope="diagram-scope",
            )
    assert session_id == "existing-session"
