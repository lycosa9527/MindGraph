"""
LIVE_LLM smoke: node-action agent against library fixture mindmap.

Uses ``tests/fixtures/prompt_requirements/mind_map_fixed.json`` (北京三日游 / 衣食住行).

Run (WSL + conda):
  LIVE_LLM=1 python -m pytest tests/test_node_action_smoke_live.py -q -s
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.kitty.routing.intent_parser import parse_one_sentence_edit_intent
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parent / "fixtures/prompt_requirements/mind_map_fixed.json"


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
    yield
    reset_httpx_clients_for_tests()


@pytest.fixture(scope="module", name="library_mindmap_context")
def _library_mindmap_context_fixture() -> dict:
    """Load Beijing trip mindmap fixture as one-sentence session context."""
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    children = spec.get("children") or []
    diagram_data = {
        "center": {"text": spec["topic"]},
        "children": [
            {"text": label, "id": f"branch-{idx}"} for idx, label in enumerate(children) if isinstance(label, str)
        ],
    }
    return {"language": "zh", "diagram_data": diagram_data}


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("utterance", "expected_action", "expected_target"),
    [
        ("补全「食」这个分支", "auto_complete_branch", "食"),
        ("删除「住」分支", "delete_node", "住"),
        ("主题改成北京五日游", "update_center", "北京五日游"),
        ("添加一个「玩」的分支", "add_node", "玩"),
    ],
    ids=["complete-branch", "delete-branch", "update-center", "add-branch"],
)
async def test_node_action_library_fixture_mindmap(
    library_mindmap_context: dict,
    utterance: str,
    expected_action: str,
    expected_target: str,
) -> None:
    """Real LLM routes edits against 北京三日游 library fixture branches."""
    cmd = await parse_one_sentence_edit_intent(
        utterance,
        voice_session_id="node_action_smoke_lib",
        diagram_type="mindmap",
        session_context=library_mindmap_context,
    )
    assert cmd.get("action") == expected_action, cmd
    target = str(cmd.get("target") or cmd.get("node_identifier") or "").strip()
    node_id = cmd.get("node_id")
    label_ok = expected_target in target or target == expected_target
    if expected_action in ("delete_node", "auto_complete_branch") and not label_ok:
        branch_ids = {
            item["text"]: item["id"]
            for item in library_mindmap_context["diagram_data"]["children"]
            if isinstance(item, dict)
        }
        label_ok = node_id == branch_ids.get(expected_target)
    assert label_ok, cmd
    if expected_action in ("delete_node", "auto_complete_branch"):
        assert isinstance(node_id, str) and node_id.startswith("branch-")
