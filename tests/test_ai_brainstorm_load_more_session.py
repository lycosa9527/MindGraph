"""Load More must keep palette sub-sessions so later batches get new node ids."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List

import pytest

from agents.ai_brainstorm.double_bubble import DoubleBubbleBrainstormGenerator
from agents.ai_brainstorm.multi_flow import MultiFlowBrainstormGenerator


async def _fake_stream(**kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield one unique line per mode and batch, then complete."""
    prompt = str(kwargs["prompt"])
    model = kwargs["models"][0]
    later = "第2批" in prompt
    if "差异对" in prompt:
        line = "磁场感应 | 金属触点 | 接触方式\n" if later else "无需插线 | 需要插线 | 供电方式\n"
    elif "相似点" in prompt:
        line = "都能储能\n" if later else "都用电能\n"
    elif "个结果" in prompt:
        line = "续航延长\n" if later else "使用更方便\n"
    else:
        line = "电池成本下降\n" if later else "充电桩不足\n"
    yield {"event": "token", "llm": model, "token": line}
    yield {
        "event": "complete",
        "llm": model,
        "duration": 0.01,
        "token_count": 8,
    }


class _FakeLLMService:
    """Stand-in so tests do not touch the process-wide LLM client."""

    stream_progressive = staticmethod(_fake_stream)


async def _node_ids(generator: Any, **kwargs: Any) -> List[str]:
    ids: List[str] = []
    async for chunk in generator.generate_batch(**kwargs):
        if chunk.get("event") != "node_generated":
            continue
        node = chunk.get("node") or {}
        node_id = node.get("id")
        if isinstance(node_id, str):
            ids.append(node_id)
    return ids


@pytest.mark.asyncio
async def test_double_bubble_load_more_keeps_batch_counter() -> None:
    """A second double-bubble batch must not reuse the first batch's node ids."""
    generator = DoubleBubbleBrainstormGenerator()
    setattr(generator, "llm_service", _FakeLLMService())
    session_id = "palette_dbl_load_more"
    common = {
        "session_id": session_id,
        "center_topic": "无线充电 vs 有线充电",
        "educational_context": {"language": "zh"},
        "_mode": "both",
        "llm_models": ["express"],
    }

    first = await _node_ids(generator, **common)
    second = await _node_ids(generator, **common)

    assert len(first) == 2
    assert len(second) == 2
    assert set(first).isdisjoint(second)
    assert all("_2_" in node_id for node_id in second)
    assert generator.batch_counts[f"{session_id}_similarities"] == 2
    assert generator.batch_counts[f"{session_id}_differences"] == 2


@pytest.mark.asyncio
async def test_multi_flow_load_more_keeps_batch_counter() -> None:
    """A second multi-flow batch must not reuse the first batch's node ids."""
    generator = MultiFlowBrainstormGenerator()
    setattr(generator, "llm_service", _FakeLLMService())
    session_id = "palette_flow_load_more"
    common = {
        "session_id": session_id,
        "center_topic": "城市推行无线充电",
        "educational_context": {"language": "zh"},
        "_mode": "both",
        "llm_models": ["express"],
    }

    first = await _node_ids(generator, **common)
    second = await _node_ids(generator, **common)

    assert len(first) == 2
    assert len(second) == 2
    assert set(first).isdisjoint(second)
    assert all("_2_" in node_id for node_id in second)
    assert generator.batch_counts[f"{session_id}_causes"] == 2
    assert generator.batch_counts[f"{session_id}_effects"] == 2
