"""
Mind-map autocomplete audit across 20 topics.

Simulates the two reported failure modes (topic drift + flat children) and asserts
the guards we shipped: locked_topic overwrite, hierarchy validation, prompt lock
wording, and end-to-end generate_graph with a drifting LLM mock.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.autocomplete_topic_lock import apply_locked_topic_to_spec, resolve_locked_topic
from agents.mind_maps.mind_map_agent import MindMapAgent

# 20 diverse teaching / canvas topics (zh + en) used for the audit matrix.
AUDIT_TOPICS: tuple[str, ...] = (
    "钢琴",
    "北京三日游计划",
    "光合作用",
    "水循环",
    "二次函数",
    "抗日战争",
    "细胞结构",
    "丝绸之路",
    "牛顿第一定律",
    "唐诗三百首",
    "Photosynthesis",
    "Water Cycle",
    "Quadratic Functions",
    "Ancient Rome",
    "Climate Change",
    "The Solar System",
    "Democracy",
    "Machine Learning Basics",
    "World War II",
    "Healthy Eating",
)

assert len(AUDIT_TOPICS) == 20


def _paraphrased_topic(topic: str) -> str:
    """Simulate LLM rewriting the canvas topic (forbidden)."""
    if any("\u4e00" <= ch <= "\u9fff" for ch in topic):
        return f"关于{topic}的思维导图"
    return f"A mind map about {topic}"


def _flat_spec(topic: str) -> dict[str, Any]:
    """DeepSeek-style flat star: leaves under topic, no nested branches."""
    return {
        "topic": _paraphrased_topic(topic),
        "children": [
            {"id": "1", "text": "Point A"},
            {"id": "2", "text": "Point B"},
            {"id": "3", "text": "Point C"},
            {"id": "4", "text": "Point D"},
            {"id": "5", "text": "Point E"},
            {"id": "6", "text": "Point F"},
        ],
    }


def _nested_spec(topic: str, *, drift_topic: bool = True) -> dict[str, Any]:
    """Valid 4-branch mind map; optionally drifts the topic field."""
    return {
        "topic": _paraphrased_topic(topic) if drift_topic else topic,
        "children": [
            {
                "id": "b1",
                "text": "Branch 1",
                "children": [{"id": "b1a", "text": "Item 1.1"}],
            },
            {
                "id": "b2",
                "text": "Branch 2",
                "children": [{"id": "b2a", "text": "Item 2.1"}],
            },
            {
                "id": "b3",
                "text": "Branch 3",
                "children": [{"id": "b3a", "text": "Item 3.1"}],
            },
            {
                "id": "b4",
                "text": "Branch 4",
                "children": [{"id": "b4a", "text": "Item 4.1"}],
            },
        ],
    }


@pytest.mark.parametrize("topic", AUDIT_TOPICS)
def test_audit_resolve_and_apply_topic_lock(topic: str) -> None:
    """Canvas topic is resolved for autocomplete and forced onto the mind-map spec."""
    resolved = resolve_locked_topic(
        topic,
        request_type="autocomplete",
        user_prompt=f"{topic}\n\nextra instructions",
    )
    assert resolved == topic

    drifted = {"topic": _paraphrased_topic(topic), "children": []}
    locked = apply_locked_topic_to_spec(drifted, topic, "mind_map")
    assert locked["topic"] == topic
    assert locked["topic"] != _paraphrased_topic(topic)


@pytest.mark.parametrize("topic", AUDIT_TOPICS)
def test_audit_rejects_flat_children_no_branches(topic: str) -> None:
    """Flat all-children trees (no nested branches) must fail hierarchy validation."""
    agent = MindMapAgent(model="qwen")
    ok, msg = agent.validate_output(_flat_spec(topic), enforce_hierarchy=True)
    assert ok is False
    assert "nested children" in msg or "4, 6, or 8" in msg


@pytest.mark.parametrize("topic", AUDIT_TOPICS)
def test_audit_accepts_nested_hierarchy(topic: str) -> None:
    """Proper branch→children nesting with even branch count passes validation."""
    agent = MindMapAgent(model="qwen")
    ok, msg = agent.validate_output(_nested_spec(topic, drift_topic=False), enforce_hierarchy=True)
    assert ok is True
    assert msg.startswith("Valid")


@pytest.mark.parametrize("topic", AUDIT_TOPICS)
@pytest.mark.asyncio
async def test_audit_generate_graph_locks_topic_and_rejects_flat(topic: str) -> None:
    """End-to-end agent: drifting nested JSON keeps topic; flat JSON fails."""
    agent = MindMapAgent(model="qwen")
    language = "zh" if any("\u4e00" <= ch <= "\u9fff" for ch in topic) else "en"
    captured: dict[str, Any] = {}

    nested_json = json.dumps(_nested_spec(topic, drift_topic=True), ensure_ascii=False)

    async def fake_nested_dispatch(**kwargs: Any) -> str:
        captured["prompt"] = kwargs.get("prompt", "")
        return nested_json

    with patch(
        "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
        new=AsyncMock(side_effect=fake_nested_dispatch),
    ):
        nested_result = await agent.generate_graph(
            topic,
            language,
            request_type="autocomplete",
            locked_topic=topic,
        )
    assert nested_result["success"] is True
    assert nested_result["spec"]["topic"] == topic
    user_prompt = str(captured.get("prompt", ""))
    assert topic in user_prompt
    assert "CRITICAL" in user_prompt

    flat_json = json.dumps(_flat_spec(topic), ensure_ascii=False)
    with patch(
        "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
        new=AsyncMock(return_value=flat_json),
    ):
        flat_result = await agent.generate_graph(
            topic,
            "en",
            request_type="autocomplete",
            locked_topic=topic,
        )
    assert flat_result["success"] is False
    error = flat_result.get("error", "")
    assert "nested children" in error or "4, 6, or 8" in error
