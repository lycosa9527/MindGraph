"""LIVE_LLM: 10 prompts × gallery / DingTalk / Kitty generate paths.

Run (WSL + conda):
  LIVE_LLM=1 python -m pytest tests/test_prompt_understanding_methods_live.py -q -s
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from agents.core.generate_pipeline import run_generate_pipeline
from agents.core.prompt_to_diagram_result import (
    coerce_prompt_to_diagram_spec,
    normalize_prompt_to_diagram_result,
)
from agents.core.prompt_to_diagram_run import attach_learning_sheet_metadata, run_prompt_to_diagram_llm
from agents.core.prompt_understanding import prepare_generation_prompt
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.infrastructure.http.error_handler import LLMServiceError, LLMTimeoutError
from services.kitty.agent_loop.fresh_diagram_generate import resolve_fresh_diagram_commands
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class LiveCase:
    """One production prompt shared by all three generate methods."""

    case_id: str
    prompt: str
    language: str
    needles: tuple[str, ...]
    level: str
    learning_sheet: bool


CASES: tuple[LiveCase, ...] = (
    LiveCase("cats_dogs_zh", "比较猫和狗", "zh", ("猫", "狗"), "general", False),
    LiveCase(
        "photo_trail",
        "画一个光合作用的思维导图，小学水平",
        "zh",
        ("光合", "光", "植物"),
        "primary",
        False,
    ),
    LiveCase(
        "photo_mid",
        "画一个小学水平的光合作用思维导图",
        "zh",
        ("光合", "光", "植物"),
        "primary",
        False,
    ),
    LiveCase("ml_expert", "机器学习，专家水平", "zh", ("机器", "学习", "模型"), "expert", False),
    LiveCase("tea_sheet", "茶叶半成品", "zh", ("茶",), "general", True),
    LiveCase("college_plan", "大学生活规划", "zh", ("大学", "生活"), "general", False),
    LiveCase("cats_dogs_en", "Compare cats and dogs", "en", ("cat", "dog"), "general", False),
    LiveCase(
        "photo_en_primary",
        "photosynthesis for primary school",
        "en",
        ("photo", "plant", "sun", "leaf"),
        "primary",
        False,
    ),
    LiveCase("beijing", "北京三日游", "zh", ("北京",), "general", False),
    LiveCase("inflation_adult", "通货膨胀，成人水平", "zh", ("通胀", "通货", "物价"), "adult", False),
)


@pytest.fixture(scope="module", autouse=True)
def _load_repo_dotenv() -> None:
    """Load ``.env`` keys without bash-sourcing (comments break ``source``)."""
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.fixture(scope="module")
def _live_llm_ready():
    """Initialize Redis + LLM once for the module."""
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run live method tests")
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


def _flatten_text(value: Any) -> str:
    parts: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, str):
            parts.append(item)
            return
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
            return
        if isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return " ".join(parts).lower()


def _has_structure(spec: dict[str, Any]) -> bool:
    list_keys = (
        "children",
        "nodes",
        "steps",
        "context",
        "analogies",
        "concepts",
        "attributes",
        "similarities",
        "left_differences",
        "right_differences",
    )
    for key in list_keys:
        value = spec.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    left = spec.get("left")
    right = spec.get("right")
    left_ok = isinstance(left, str) and bool(left.strip())
    right_ok = isinstance(right, str) and bool(right.strip())
    return left_ok and right_ok


def _assert_prepared(case: LiveCase) -> None:
    prepared = prepare_generation_prompt(case.prompt, case.language)
    assert prepared.ai_content_level == case.level
    assert prepared.is_learning_sheet is case.learning_sheet
    if case.learning_sheet:
        assert "半成品" not in prepared.topic_prompt
        assert "学习单" not in prepared.topic_prompt
    if case.level != "general":
        assert prepared.generation_instructions
        assert "小学水平" not in prepared.topic_prompt
        assert "专家水平" not in prepared.topic_prompt
        assert "成人水平" not in prepared.topic_prompt
        assert "primary school" not in prepared.topic_prompt.lower()


def _assert_spec(case: LiveCase, spec: dict[str, Any], *, learning_sheet: bool) -> None:
    assert isinstance(spec, dict)
    assert spec.get("error") in (None, "")
    assert _has_structure(spec)
    blob = _flatten_text(spec)
    assert any(needle.lower() in blob for needle in case.needles), blob[:400]
    assert bool(spec.get("is_learning_sheet")) is learning_sheet


def _fresh_kitty_context() -> dict[str, Any]:
    return {
        "one_sentence_phase": "create",
        "diagram_type": "mind_map",
        "diagram_data": {
            "center": {"text": "中心主题"},
            "children": [],
            "nodes": [{"id": "topic", "type": "topic", "text": "中心主题"}],
        },
    }


async def _gallery(case: LiveCase) -> dict[str, Any]:
    prepared = prepare_generation_prompt(case.prompt, case.language)
    return await run_generate_pipeline(
        prepared.merged_prompt(),
        language=case.language,
        model="qwen",
        request_type="diagram_generation",
        endpoint_path="/api/generate_graph",
        generation_instructions=prepared.generation_instructions,
        is_learning_sheet=prepared.is_learning_sheet,
    )


async def _dingtalk(case: LiveCase) -> dict[str, Any]:
    run = await run_prompt_to_diagram_llm(
        prompt=case.prompt,
        language=case.language,
        user_id=None,
        organization_id=None,
        api_key_id=None,
        endpoint_path="/api/generate_dingtalk",
    )
    assert run.missing_template is False
    assert run.empty_response is False
    normalized = normalize_prompt_to_diagram_result(run.raw_result)
    assert normalized is not None
    spec = normalized.get("spec")
    assert isinstance(spec, dict)
    diagram_type = str(normalized.get("diagram_type") or "bubble_map")
    spec = coerce_prompt_to_diagram_spec(spec, diagram_type)
    return attach_learning_sheet_metadata(spec, run.prepared.is_learning_sheet)


async def _kitty(case: LiveCase) -> dict[str, Any]:
    understood = prepare_generation_prompt(case.prompt, case.language)
    commands = resolve_fresh_diagram_commands(
        case.prompt,
        _fresh_kitty_context(),
        case.language,
        prepared=understood,
    )
    assert commands is not None
    complete = next(item for item in commands if item.get("action") == "auto_complete")
    topic = str(complete.get("topic") or "").strip()
    assert topic
    canvas_prompt = f"{topic} 半成品" if complete.get("is_learning_sheet") is True else topic
    canvas = prepare_generation_prompt(
        canvas_prompt,
        case.language,
        explicit_instructions=understood.generation_instructions,
    )
    return await run_generate_pipeline(
        canvas.merged_prompt(),
        language=case.language,
        forced_diagram_type="mind_map",
        model="qwen",
        request_type="autocomplete",
        endpoint_path="/api/generate_graph",
        generation_instructions=canvas.generation_instructions,
        is_learning_sheet=canvas.is_learning_sheet,
    )


async def _retry(factory: Callable[[], Awaitable[Any]]) -> Any:
    last: BaseException | None = None
    for _ in range(2):
        try:
            return await factory()
        except (LLMTimeoutError, LLMServiceError, *LLM_PIPELINE_ERRORS) as exc:
            last = exc
    assert last is not None
    raise last


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[item.case_id for item in CASES])
async def test_live_gallery_generate_graph(case: LiveCase) -> None:
    """Landing generate_graph: shared prepare + 3-step pipeline."""
    _assert_prepared(case)
    result = await _retry(lambda: _gallery(case))
    assert result.get("success") is True
    spec = result.get("spec")
    assert isinstance(spec, dict)
    _assert_spec(case, spec, learning_sheet=case.learning_sheet)
    assert bool(result.get("is_learning_sheet")) is case.learning_sheet


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[item.case_id for item in CASES])
async def test_live_dingtalk_prompt_to_diagram(case: LiveCase) -> None:
    """DingTalk / PNG one-shot LLM (no Playwright)."""
    _assert_prepared(case)
    spec = await _retry(lambda: _dingtalk(case))
    _assert_spec(case, spec, learning_sheet=case.learning_sheet)


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[item.case_id for item in CASES])
async def test_live_kitty_fresh_autocomplete(case: LiveCase) -> None:
    """Fresh Kitty extract + canvas auto_complete generate_graph."""
    _assert_prepared(case)
    result = await _retry(lambda: _kitty(case))
    assert result.get("success") is True
    spec = result.get("spec")
    assert isinstance(spec, dict)
    _assert_spec(case, spec, learning_sheet=case.learning_sheet)
    assert bool(result.get("is_learning_sheet")) is case.learning_sheet
