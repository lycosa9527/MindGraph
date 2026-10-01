"""Extracted-content prompts stay a topic for type agents and a source for comparisons."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.diagram import content_diagram_generate as mod
from services.diagram.content_diagram_generate import (
    content_agent_user_prompt,
    resolve_content_diagram_slug,
)


def test_resolve_content_diagram_slug_defaults_to_mindmap() -> None:
    """Blank and mind-map aliases stay on the content agent."""
    assert resolve_content_diagram_slug(None) == "mindmap"
    assert resolve_content_diagram_slug("mind_map") == "mindmap"
    assert resolve_content_diagram_slug("circle_map") == "circle_map"


def test_resolve_content_diagram_slug_rejects_unknown() -> None:
    """Unknown slugs must not silently become a mind map."""
    with pytest.raises(ValueError):
        resolve_content_diagram_slug("not_a_diagram")


def test_short_topic_ignores_filename_and_body() -> None:
    """Circle-map prompts use the heading, not the filename or the full source."""
    prompt = content_agent_user_prompt(
        "circle_map",
        page_title="lesson.pdf",
        page_content="# 光合作用\n\n叶绿体把光能变成化学能。" * 20,
        topic_hint=None,
    )
    assert prompt == "光合作用"


def test_double_bubble_keeps_source_excerpt() -> None:
    """Comparison maps keep a clipped source so both topics can be found."""
    body = "比较猫和狗。猫独立，狗合群。" + ("细节" * 400)
    prompt = content_agent_user_prompt(
        "double_bubble_map",
        page_title="notes.docx",
        page_content=body,
        topic_hint="猫和狗",
    )
    assert prompt.startswith("猫和狗\n")
    assert "猫独立" in prompt
    assert len(prompt) < len(body)


@pytest.mark.asyncio
async def test_non_mindmap_calls_that_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A circle map request calls CircleMapAgent with the short topic."""
    agent = MagicMock()
    agent.generate_graph = AsyncMock(
        return_value={"success": True, "spec": {"topic": "光合作用", "context": ["叶绿体"]}}
    )

    def _get_agent(slug: str):
        assert slug == "circle_map"
        return agent

    monkeypatch.setattr(mod, "get_agent", _get_agent)
    result = await mod.generate_non_mindmap_from_content(
        diagram_type="circle_map",
        page_content="# 光合作用\n\n叶绿体。",
        language="zh",
        page_title="lesson.pdf",
        topic_hint=None,
        user_id=1,
        organization_id=None,
        endpoint_path="/api/canvas/generate_mindmap_from_package",
        generation_instructions=None,
    )

    assert result["diagram_type"] == "circle_map"
    agent.generate_graph.assert_awaited_once()
    assert agent.generate_graph.await_args.args[0] == "光合作用"
