"""
Live integration tests for prompt understanding layer.

Requires QWEN_API_KEY, REDIS_URL, and init_redis_sync + llm_service.initialize().

Run manually:
  LIVE_LLM=1 python -m pytest tests/test_prompt_requirements_live.py -q -s
"""

from __future__ import annotations

import os

import pytest

from agents.core.prompt_requirements import extract_prompt_requirements
from agents.core.workflow import agent_graph_workflow_with_styles
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync

BEIJING_PROMPT = "生成一个北京三日游计划，四个分支，衣食住行四个方面"
EXPECTED_BRANCHES = ["衣", "食", "住", "行"]

pytestmark = pytest.mark.integration


def _live_llm_enabled() -> bool:
    if os.getenv("LIVE_LLM", "").strip() not in ("1", "true", "yes"):
        return False
    api_key = (os.getenv("QWEN_API_KEY") or "").strip()
    return bool(api_key) and "your-" not in api_key


@pytest.fixture(scope="module")
def _live_llm_ready():
    """Initialize Redis + LLM clients once for live tests."""
    if not _live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run live LLM tests")
    init_redis_sync()
    llm_service.initialize()
    yield


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
async def test_live_requirements_extraction_mind_map_fixed() -> None:
    """Stage 2 should extract fixed branches from Beijing travel prompt."""
    parsed = await extract_prompt_requirements(
        BEIJING_PROMPT,
        "mind_map",
        language="zh",
        model="qwen",
        request_type="prompt_requirements_live_test",
    )
    assert parsed.structure_mode == "fixed"
    assert "北京" in parsed.central
    children = parsed.fixed_nodes.get("children") or []
    assert len(children) >= 4


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
async def test_live_workflow_mind_map_preserves_branch_labels() -> None:
    """Full workflow should honor user branch labels verbatim."""
    result = await agent_graph_workflow_with_styles(
        BEIJING_PROMPT,
        language="zh",
        forced_diagram_type="mind_map",
        model="qwen",
        request_type="prompt_requirements_live_test",
    )
    assert result.get("success") is True
    assert result.get("structure_mode") == "fixed"
    assert result.get("topics") == ["北京三日游计划"]

    spec = result.get("spec") or {}
    branch_labels = [
        (child.get("text") or child.get("label") or "").strip()
        for child in (spec.get("children") or [])
        if isinstance(child, dict)
    ]
    assert branch_labels == EXPECTED_BRANCHES
