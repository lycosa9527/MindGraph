"""LIVE_LLM: every library node action on five real mindmaps.

Run (WSL + conda):
  LIVE_LLM=1 python -m pytest tests/test_kitty_agent_loop_five_maps_live.py -q -s
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import dispatch_loop_tool as real_dispatch_loop_tool
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.kitty_agent_loop_catalog import (
    NODE_ACTIONS,
    STRUCTURAL_ACTIONS,
    load_all_real_mindmaps,
    utterance_for,
)
from tests.kitty_agent_loop_timing import (
    CaseTiming,
    TimingSink,
    format_summary,
    write_timing_json,
)
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import mock_await_args

pytestmark = pytest.mark.integration

_MAPS = load_all_real_mindmaps()
_CASES = [(mmap.slug, action) for mmap in _MAPS for action in NODE_ACTIONS]
_MAP_BY_SLUG = {mmap.slug: mmap for mmap in _MAPS}
_TIMINGS = TimingSink()
_TIMING_JSON = Path("/tmp/kitty_five_maps_live_timings.json")


@pytest.fixture(scope="module", autouse=True)
def _load_repo_dotenv() -> None:
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.fixture(scope="module")
def _live_llm_ready():
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run live smoke tests")
    init_redis_sync()
    llm_service.initialize()
    yield
    reset_httpx_clients_for_tests()


@pytest.fixture(autouse=True)
def _reset_httpx_per_test():
    reset_httpx_clients_for_tests()
    llm_service.initialize()
    yield
    reset_httpx_clients_for_tests()


@pytest.fixture(scope="module", autouse=True)
def _print_timing_summary():
    yield
    summary = format_summary(_TIMINGS)
    print(summary)
    write_timing_json(_TIMINGS, _TIMING_JSON)
    print(f"wrote {_TIMING_JSON}")


def _applied(action: str, node_id: Optional[str]) -> DiagramCommandResult:
    applied_ops = [{"op": action, "node_id": node_id}] if node_id else [{"op": action}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="five-live",
            revision=2,
            applied_ops=applied_ops,
        ),
        hub_revision=2,
    )


def _first_tool_name(recorded: List[Dict[str, Any]]) -> str:
    for row in recorded:
        calls = row.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            continue
        first = calls[0]
        if not isinstance(first, dict):
            continue
        fn = first.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str):
            return fn["name"]
    return ""


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize(("slug", "action"), _CASES, ids=[f"{s}-{a}" for s, a in _CASES])
async def test_five_maps_all_node_actions_live(slug: str, action: str) -> None:
    """Real qwen3.6-flash picks the matching library tool on each real map."""
    mmap = _MAP_BY_SLUG[slug]
    utterance = utterance_for(mmap, action)
    ws = MagicMock()
    vid = create_voice_session(
        user_id="live-audit",
        diagram_session_id=f"scope-{slug}-live",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = mmap.context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    bus_mock = AsyncMock(side_effect=lambda *_a, **_k: _applied(action, mmap.branch_id))
    branch_mock = AsyncMock(return_value=True)
    start_ac_mock = AsyncMock(return_value=True)
    ws_mock = AsyncMock(return_value=True)
    real_chat = llm_service.chat_raw
    recorded: List[Dict[str, Any]] = []
    llm_ms = 0.0
    dispatch_ms = 0.0
    dispatch_n = 0

    async def _chat(*args: Any, **kwargs: Any) -> Any:
        nonlocal llm_ms
        kwargs["timeout"] = 30.0
        started = time.perf_counter()
        result = await real_chat(*args, **kwargs)
        llm_ms += (time.perf_counter() - started) * 1000.0
        if isinstance(result, dict):
            recorded.append(result)
        return result

    async def _dispatch(
        websocket: Any,
        voice_session_id: str,
        *,
        name: str,
        arguments_json: str,
        session_context: Dict[str, Any],
        diagram_type: str,
        command_text: str,
        verify_required: bool,
    ) -> Any:
        nonlocal dispatch_ms, dispatch_n
        started = time.perf_counter()
        result = await real_dispatch_loop_tool(
            websocket,
            voice_session_id,
            name=name,
            arguments_json=arguments_json,
            session_context=session_context,
            diagram_type=diagram_type,
            command_text=command_text,
            verify_required=verify_required,
        )
        dispatch_ms += (time.perf_counter() - started) * 1000.0
        dispatch_n += 1
        return result

    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=_chat),
            patch("services.kitty.agent_loop.loop.dispatch_loop_tool", new=_dispatch),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", branch_mock),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                start_ac_mock,
            ),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
            loop_started = time.perf_counter()
            result = await run_typed_agent_loop(ws, vid, utterance, dict(mmap.context))
            total_ms = (time.perf_counter() - loop_started) * 1000.0

        tool_name = _first_tool_name(recorded)
        _TIMINGS.add(
            CaseTiming(
                slug=slug,
                action=action,
                total_ms=total_ms,
                llm_ms=llm_ms,
                dispatch_ms=dispatch_ms,
                dispatch_n=dispatch_n,
                tool=tool_name,
                reason=str(result.reason or ""),
            )
        )
        print(
            f"\n[{slug}/{action}] total={total_ms / 1000:.2f}s llm={llm_ms / 1000:.2f}s "
            f"dispatch={dispatch_ms:.1f}ms n={dispatch_n} reason={result.reason} tool={tool_name}"
        )
        assert result.outcome == RouteOutcome.EXECUTED, result
        assert result.reason != "heuristic", result
        assert result.reason != "thinking_coins", result
        if action in STRUCTURAL_ACTIONS:
            expected_tool = f"diagram.{action}"
            assert tool_name == expected_tool or result.action == action, (tool_name, result)
            bus_mock.assert_awaited()
            command = mock_await_args(bus_mock)[2]
            assert command.get("action") == action, command
            if action in {"update_node", "delete_node"}:
                node_id = str(command.get("node_id") or "")
                assert node_id == mmap.branch_id, command
                assert not is_leftover_mindmap_branch_id(node_id)
            if action == "add_node":
                assert "扩展阅读" in str(command.get("target") or ""), command
                start_ac_mock.assert_awaited()
                assert start_ac_mock.await_args is not None
                assert start_ac_mock.await_args.kwargs.get("node_id") == mmap.branch_id
                assert result.reason == "await_canvas"
            if action == "update_center":
                assert "导学" in str(command.get("target") or "") or mmap.topic in str(command.get("target") or ""), (
                    command
                )
        elif action == "auto_complete_branch":
            assert tool_name == "node_action.auto_complete_branch", tool_name
            branch_mock.assert_awaited()
            kwargs = branch_mock.await_args.kwargs if branch_mock.await_args else {}
            target = str(kwargs.get("target") or "")
            if not target and branch_mock.await_args is not None:
                args = branch_mock.await_args.args
                if len(args) >= 3:
                    target = str(args[2])
            node_id = str(kwargs.get("node_id") or "")
            assert node_id == mmap.branch_id or mmap.branch_label in target
        elif action == "auto_complete":
            assert tool_name == "node_action.auto_complete", tool_name
            ws_mock.assert_awaited()
        elif action == "clarify_options":
            assert tool_name == "node_action.clarify_options", tool_name
            assert result.action == "clarify_options"
            pending = voice_sessions[vid].get("pending_clarify_options")
            assert isinstance(pending, dict)
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("slug", [mmap.slug for mmap in _MAPS], ids=[mmap.slug for mmap in _MAPS])
async def test_add_brand_branch_starts_autocomplete_live(slug: str) -> None:
    """Same user line as the 枕头 session: add a named branch, then silent complete."""
    mmap = _MAP_BY_SLUG[slug]
    utterance = "添加一个品牌的分支"
    ws = MagicMock()
    vid = create_voice_session(
        user_id="live-brand",
        diagram_session_id=f"scope-{slug}-brand",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = mmap.context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    created = f"uid-brand-{slug}"
    bus_mock = AsyncMock(return_value=_applied("add_node", created))
    start_ac_mock = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", llm_service.chat_raw),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                start_ac_mock,
            ),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
            result = await run_typed_agent_loop(ws, vid, utterance, dict(mmap.context))
        print(f"\n[{slug}/品牌] outcome={result.outcome} action={result.action} reason={result.reason}")
        assert result.outcome == RouteOutcome.EXECUTED, result
        assert result.action == "add_node", result
        assert result.reason == "await_canvas", result
        bus_mock.assert_awaited()
        command = mock_await_args(bus_mock)[2]
        assert command.get("action") == "add_node", command
        assert "品牌" in str(command.get("target") or ""), command
        start_ac_mock.assert_awaited()
        assert start_ac_mock.await_args is not None
        assert start_ac_mock.await_args.kwargs.get("node_id") == created
    finally:
        voice_sessions.pop(vid, None)
