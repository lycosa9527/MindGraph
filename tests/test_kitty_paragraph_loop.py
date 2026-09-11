"""Long paste uses the typed flash tool loop, not a qwen-plus extractor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.agent_loop.loop import AGENT_LOOP_MODEL, run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome, RouteResult
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


@pytest.mark.asyncio
async def test_paragraph_runs_flash_tool_loop() -> None:
    """Long paste calls qwen3.8-flash tools; there is no paragraph extractor."""
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
    chat_mock = AsyncMock(return_value={"content": "好", "tool_calls": []})
    clarify = AsyncMock(
        return_value=RouteResult(outcome=RouteOutcome.EXECUTED, reason="intent_clarify", action="clarify")
    )
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.loop._offer_intent_clarify", clarify),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
            patch("services.kitty.agent_loop.loop.fanout_voice_phase_from_session", new=AsyncMock()),
        ):
            result = await run_typed_agent_loop(ws, vid, _PARAGRAPH, dict(context))
        assert result.reason != "fast_structural"
        chat_mock.assert_awaited()
        assert chat_mock.await_args is not None
        assert chat_mock.await_args.kwargs["model"] == AGENT_LOOP_MODEL
    finally:
        voice_sessions.pop(vid, None)
