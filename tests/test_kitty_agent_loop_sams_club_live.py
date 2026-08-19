"""LIVE_LLM: typed agent loop against the real 山姆会员商店 mindmap.

Run (WSL + conda):
  LIVE_LLM=1 python -m pytest tests/test_kitty_agent_loop_sams_club_live.py -q -s
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import mock_await_args

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parent / "fixtures/zhihui_sams_club_l1.json"
COMPETITOR_UID = "7b1257c0-5091-4d7b-9985-410a104d56cb"


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


def _hydrated_context() -> Dict[str, Any]:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = diagram_data_from_saved_spec(spec, "mindmap")
    return {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_data": live,
    }


def _applied(action: str, node_id: str | None = None) -> DiagramCommandResult:
    applied_ops = [{"op": action, "node_id": node_id}] if node_id else [{"op": action}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="live-sams",
            revision=2,
            applied_ops=applied_ops,
        ),
        hub_revision=2,
    )


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("utterance", "expected_action", "expected_node_id"),
    [
        ("删除竞争对手这个分支", "delete_node", COMPETITOR_UID),
        ("主题改成山姆会员店分析", "update_center", None),
        ("添加一个会员制度的分支", "add_node", None),
    ],
    ids=["delete-competitor", "update-center", "add-member-policy"],
)
async def test_live_sams_club_agent_loop(
    utterance: str,
    expected_action: str,
    expected_node_id: str | None,
) -> None:
    """Real qwen3.6-flash tool loop against the Sam's Club snapshot."""
    context = _hydrated_context()
    ws = MagicMock()
    vid = create_voice_session(user_id="live-audit", diagram_session_id="scope-sams-live", diagram_type="mindmap")
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    bus_mock = AsyncMock(side_effect=lambda *_args, **_kwargs: _applied(expected_action, expected_node_id))
    real_chat = llm_service.chat_raw

    async def _chat(*args: Any, **kwargs: Any) -> Any:
        kwargs["timeout"] = 30.0
        return await real_chat(*args, **kwargs)

    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=_chat),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
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
            result = await run_typed_agent_loop(ws, vid, utterance, dict(context))

        print(f"\n[sams-live] reason={result.reason} action={result.action} bus={bus_mock.await_count}")
        assert result.outcome == RouteOutcome.EXECUTED, result
        assert result.reason != "heuristic", result
        assert bus_mock.await_count >= 1, result
        command = mock_await_args(bus_mock)[2]
        print(f"[sams-live] command={command}")
        assert command.get("action") == expected_action, command
        if expected_node_id:
            assert command.get("node_id") == expected_node_id, command
        if expected_action == "add_node":
            assert "会员" in str(command.get("target") or "")
        if expected_action == "update_center":
            assert "山姆" in str(command.get("target") or "")
    finally:
        voice_sessions.pop(vid, None)
