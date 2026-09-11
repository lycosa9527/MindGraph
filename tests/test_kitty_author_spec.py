"""author_spec cookbook mind-map save."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.diagram.semantic_spec_validation import validate_semantic_spec
from services.kitty.agent_loop.author_spec import (
    build_mindmap_spec,
    dispatch_author_spec,
)
from services.kitty.agent_loop.tools import loop_tool_schemas
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions


def test_build_mindmap_spec_is_valid() -> None:
    """Topic + branches pass semantic validation."""
    spec = build_mindmap_spec("市场部", ["销售", "运营"], lang="zh")
    ok, issues, normalized = validate_semantic_spec("mind_map", spec)
    assert ok, issues
    assert normalized == "mind_map"
    assert spec["topic"] == "市场部"
    assert len(spec["children"]) == 2


def test_author_spec_in_edit_and_general_schemas() -> None:
    """author_spec is available in both loop modes."""
    edit_names = {item["function"]["name"] for item in loop_tool_schemas("edit")}
    general_names = {item["function"]["name"] for item in loop_tool_schemas("general")}
    assert "author_spec" in edit_names
    assert "author_spec" in general_names


@pytest.mark.asyncio
async def test_dispatch_author_spec_saves_library() -> None:
    """Successful save returns the new diagram id."""
    sid = create_voice_session(
        user_id="4",
        diagram_session_id="scope-author",
        diagram_type="mind_map",
    )
    try:
        with patch(
            "services.kitty.agent_loop.author_spec.try_save_diagram_to_library",
            new_callable=AsyncMock,
            return_value="diag-1",
        ) as save:
            payload = await dispatch_author_spec(
                sid,
                arguments_json='{"topic":"旅行","branches":["交通","住宿"]}',
                lang="zh",
            )
        assert payload["status"] == "ok"
        assert payload["diagram_id"] == "diag-1"
        save.assert_awaited_once()
    finally:
        voice_sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_dispatch_author_spec_rejects_empty_topic() -> None:
    """Missing topic does not hit the library."""
    sid = create_voice_session(
        user_id="4",
        diagram_session_id="scope-author-empty",
        diagram_type="mind_map",
    )
    try:
        payload = await dispatch_author_spec(sid, arguments_json="{}", lang="zh")
        assert payload["status"] == "rejected"
        assert payload["error_code"] == "missing_topic"
    finally:
        voice_sessions.pop(sid, None)
