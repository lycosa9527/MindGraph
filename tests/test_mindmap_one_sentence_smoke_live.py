"""
LIVE_LLM smoke: full mindmap one-sentence pipeline (EN + ZH).

Covers:
  1. Real LLM diagram generation (spec)
  2. Intent parse for add / delete / update / center (real LLM when needed)
  3. Structural apply + verification
  4. Layout preservation (existing node positions must not move)
  5. Auto-complete regeneration with real LLM

Run (WSL + conda):
  LIVE_LLM=1 python -m pytest tests/test_mindmap_one_sentence_smoke_live.py -q -s
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from agents.core.workflow import agent_graph_workflow_with_styles
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.infrastructure.http.error_handler import LLMServiceError, LLMTimeoutError
from services.kitty.routing.intent_parser import parse_one_sentence_edit_intent
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS
from tests.smoke.mindmap_smoke_helpers import (
    apply_add_branch,
    apply_delete_node_by_label,
    apply_update_center,
    apply_update_node_label,
    assert_add_branch_verified,
    assert_layout_preserved,
    canvas_branch_labels,
    live_llm_enabled,
    mindmap_smoke_helpers_load_dotenv,
    mindmap_spec_to_canvas,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _load_repo_dotenv() -> None:
    """Load ``.env`` keys without bash-sourcing (comments break ``source``)."""
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.fixture(scope="module")
def _live_llm_ready():
    """Initialize Redis + LLM once for the smoke module."""
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run live smoke tests")
    init_redis_sync()
    llm_service.initialize()
    yield
    reset_httpx_clients_for_tests()


@pytest.fixture(autouse=True)
def _reset_httpx_per_test():
    """Avoid httpx clients bound to a previous pytest event loop."""
    reset_httpx_clients_for_tests()
    yield
    reset_httpx_clients_for_tests()


async def _generate_mindmap_canvas(prompt: str, language: str) -> dict:
    try:
        result = await agent_graph_workflow_with_styles(
            prompt,
            language=language,
            forced_diagram_type="mind_map",
            model="qwen",
            request_type="mindmap_smoke_live",
            use_rag=False,
        )
    except (LLMTimeoutError, LLMServiceError, *LLM_PIPELINE_ERRORS) as exc:
        pytest.skip(f"Live LLM unavailable for generation: {exc}")

    if not result.get("success"):
        pytest.skip(f"generation unsuccessful: {result}")
    spec = result.get("spec") or {}
    assert isinstance(spec, dict)
    assert str(spec.get("topic") or "").strip(), "empty topic from LLM"
    children = spec.get("children") or []
    assert isinstance(children, list) and len(children) >= 2, f"expected >=2 branches, got {children!r}"
    canvas = mindmap_spec_to_canvas(spec)
    assert len(canvas["nodes"]) >= 3
    assert layout_has_positions(canvas)
    return canvas


def layout_has_positions(canvas: dict) -> bool:
    """Return True when every canvas node has numeric x/y positions."""
    nodes = canvas.get("nodes") or []
    return all(
        isinstance(n, dict)
        and isinstance(n.get("position"), dict)
        and isinstance(n["position"].get("x"), (int, float))
        and isinstance(n["position"].get("y"), (int, float))
        for n in nodes
    )


async def _assert_intent_add(text: str, expected_label: str) -> None:
    cmd = await parse_one_sentence_edit_intent(
        text,
        voice_session_id="smoke_live_add",
        diagram_type="mindmap",
    )
    assert cmd.get("action") == "add_node", cmd
    assert str(cmd.get("target") or "").strip() == expected_label


async def _assert_intent_update_center(text: str, expected_topic: str) -> None:
    cmd = await parse_one_sentence_edit_intent(
        text,
        voice_session_id="smoke_live_center",
        diagram_type="mindmap",
    )
    assert cmd.get("action") == "update_center", cmd
    assert str(cmd.get("target") or "").strip() == expected_topic


async def _assert_intent_delete(text: str, expected_label: str) -> None:
    cmd = await parse_one_sentence_edit_intent(
        text,
        voice_session_id="smoke_live_delete",
        diagram_type="mindmap",
    )
    assert cmd.get("action") == "delete_node", cmd
    assert str(cmd.get("target") or "").strip() == expected_label


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "gen_prompt", "add_phrase", "add_label", "center_phrase", "center_label"),
    [
        (
            "zh",
            "生成一个关于茶叶的思维导图，四个分支",
            "添加一个饮品分析的分支",
            "饮品分析",
            "主题改成中国茶",
            "中国茶",
        ),
        (
            "en",
            "Generate a mind map about coffee with four main branches",
            "add a branch called Brewing Methods",
            "Brewing Methods",
            "change the topic to Specialty Coffee",
            "Specialty Coffee",
        ),
    ],
    ids=["zh", "en"],
)
async def test_smoke_generate_add_update_delete_layout(
    language: str,
    gen_prompt: str,
    add_phrase: str,
    add_label: str,
    center_phrase: str,
    center_label: str,
) -> None:
    """Generate → add branch → rename → delete → center; layout stays intact."""
    canvas = await _generate_mindmap_canvas(gen_prompt, language)
    baseline_labels = canvas_branch_labels(canvas)
    assert len(baseline_labels) >= 2

    # Intent: add branch (heuristic or qwen3.6-flash)
    await _assert_intent_add(add_phrase, add_label)

    before_add = copy.deepcopy(canvas)
    canvas = apply_add_branch(canvas, add_label, side="right")
    assert_layout_preserved(before_add["nodes"], canvas["nodes"])
    assert_add_branch_verified(before_add, canvas, add_label)
    assert add_label in canvas_branch_labels(canvas)

    # Rename an original branch (not the one we just added)
    rename_from = baseline_labels[0]
    rename_to = f"{rename_from}-A.1" if language == "en" else f"{rename_from}·改"
    before_rename = copy.deepcopy(canvas)
    canvas = apply_update_node_label(canvas, rename_from, rename_to)
    assert_layout_preserved(before_rename["nodes"], canvas["nodes"])
    labels_after_rename = canvas_branch_labels(canvas)
    assert rename_to in labels_after_rename
    assert rename_from not in labels_after_rename

    # Delete the added branch (intent + apply)
    if language == "zh":
        await _assert_intent_delete(f"删除{add_label}分支", add_label)
    else:
        await _assert_intent_delete(f"delete the branch called {add_label}", add_label)
    before_delete = copy.deepcopy(canvas)
    canvas, removed_id = apply_delete_node_by_label(canvas, add_label)
    assert_layout_preserved(
        before_delete["nodes"],
        canvas["nodes"],
        allow_removed_ids={removed_id},
    )
    assert add_label not in canvas_branch_labels(canvas)

    # Update center via intent + apply
    await _assert_intent_update_center(center_phrase, center_label)
    before_center = copy.deepcopy(canvas)
    canvas = apply_update_center(canvas, center_label)
    assert_layout_preserved(before_center["nodes"], canvas["nodes"])
    topic = next(n for n in canvas["nodes"] if n.get("id") == "topic")
    assert topic.get("text") == center_label


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "seed_prompt", "autocomplete_prompt"),
    [
        (
            "zh",
            "生成一个关于茶叶的思维导图，四个分支",
            "主题/描述：茶叶\n请补充更完整的教学向思维导图结构",
        ),
        (
            "en",
            "Generate a mind map about coffee with four main branches",
            "Topic/description: coffee\nExpand into a clearer teaching mind map",
        ),
    ],
    ids=["zh-autocomplete", "en-autocomplete"],
)
async def test_smoke_autocomplete_regenerates_spec(
    language: str,
    seed_prompt: str,
    autocomplete_prompt: str,
) -> None:
    """Auto-complete path: second real LLM generation still yields a valid mindmap."""
    seed = await _generate_mindmap_canvas(seed_prompt, language)
    seed_topic = str(seed.get("topic") or "")

    try:
        result = await agent_graph_workflow_with_styles(
            autocomplete_prompt,
            language=language,
            forced_diagram_type="mind_map",
            model="qwen",
            request_type="mindmap_smoke_autocomplete",
            use_rag=False,
            mind_map_topic=seed_topic,
        )
    except (LLMTimeoutError, LLMServiceError, *LLM_PIPELINE_ERRORS) as exc:
        pytest.skip(f"Live LLM unavailable for autocomplete: {exc}")

    if not result.get("success"):
        pytest.skip(f"autocomplete unsuccessful: {result}")
    spec = result.get("spec") or {}
    assert isinstance(spec, dict)
    children = spec.get("children") or []
    assert isinstance(children, list) and len(children) >= 2
    # Full regenerate may replace layout; new canvas must still have positions.
    canvas = mindmap_spec_to_canvas(spec)
    assert layout_has_positions(canvas)
    assert len(canvas_branch_labels(canvas)) >= 2


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
async def test_smoke_add_branch_a1_chinese_and_english() -> None:
    """Explicit A.1 branch add in both languages with layout guard."""
    zh_canvas = await _generate_mindmap_canvas(
        "生成一个关于茶叶的思维导图，四个分支",
        "zh",
    )
    en_canvas = await _generate_mindmap_canvas(
        "Generate a mind map about coffee with four main branches",
        "en",
    )

    await _assert_intent_add("添加一个A.1分支", "A.1")
    await _assert_intent_add("add a branch called A.1", "A.1")

    for canvas in (zh_canvas, en_canvas):
        before = copy.deepcopy(canvas)
        after = apply_add_branch(canvas, "A.1", side="right")
        assert_layout_preserved(before["nodes"], after["nodes"])
        assert_add_branch_verified(before, after, "A.1")
        assert "A.1" in canvas_branch_labels(after)
