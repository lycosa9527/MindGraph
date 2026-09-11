"""Long paste is a fast tool on the typed loop, not a second editor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.diagram.diagram_utils import is_paragraph_text
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRODUCTION_ROOTS = (
    _REPO_ROOT / "services",
    _REPO_ROOT / "routers",
)

_PARAGRAPH = (
    "光合作用是绿色植物利用光能把二氧化碳和水合成有机物并释放氧气的过程。它发生在叶绿体中。第一是光反应。第二是暗反应。"
)


def test_no_production_route_voice_command() -> None:
    """The old router door is gone from production Python."""
    hits: list[str] = []
    for root in _PRODUCTION_ROOTS:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "route_voice_command" in text:
                hits.append(str(path.relative_to(_REPO_ROOT)))
    assert not hits


def test_paragraph_detector_accepts_multi_sentence_zh() -> None:
    """Chinese lesson paste is a paragraph; a short command is not."""
    assert is_paragraph_text(_PARAGRAPH) is True
    assert is_paragraph_text("主题改成光合作用") is False


@pytest.mark.asyncio
async def test_paragraph_runs_inside_typed_loop() -> None:
    """Long paste calls the paragraph job and never opens chat_raw."""
    context = {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_type": "mind_map",
        "diagram_data": {"center": {"text": "主题"}, "children": []},
    }
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-paragraph",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    paragraph_mock = AsyncMock(return_value=True)
    chat_mock = AsyncMock()
    try:
        with (
            patch("services.kitty.agent_loop.loop.process_paragraph_with_qwen_plus", paragraph_mock),
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, _PARAGRAPH, dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "paragraph"
        paragraph_mock.assert_awaited_once()
        chat_mock.assert_not_awaited()
    finally:
        voice_sessions.pop(vid, None)
