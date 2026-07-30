"""Tests for autocomplete topic lock and mind-map hierarchy validation."""

from agents.core.autocomplete_topic_lock import (
    apply_locked_topic_to_spec,
    resolve_locked_topic,
)
from agents.mind_maps.mind_map_agent import MindMapAgent


def test_resolve_locked_topic_autocomplete_uses_explicit() -> None:
    """Explicit locked_topic wins for autocomplete requests."""
    assert (
        resolve_locked_topic(
            "钢琴",
            request_type="autocomplete",
            user_prompt="ignored\nmore",
        )
        == "钢琴"
    )


def test_resolve_locked_topic_skips_non_autocomplete() -> None:
    """Non-autocomplete request types do not lock a topic."""
    assert (
        resolve_locked_topic(
            "钢琴",
            request_type="diagram_generation",
            user_prompt="钢琴",
        )
        == ""
    )


def test_resolve_locked_topic_falls_back_to_first_prompt_line() -> None:
    """Without explicit lock, use the first non-empty prompt line."""
    assert (
        resolve_locked_topic(
            None,
            request_type="autocomplete",
            user_prompt="北京三日游\n\n生成要求\n多写细节",
        )
        == "北京三日游"
    )


def test_apply_locked_topic_mind_map_and_brace() -> None:
    """Overwrite central topic fields for mind/brace/flow maps."""
    mind = apply_locked_topic_to_spec({"topic": "wrong"}, "钢琴", "mindmap")
    assert mind["topic"] == "钢琴"

    brace = apply_locked_topic_to_spec({"whole": "wrong", "topic": "x"}, "植物", "brace_map")
    assert brace["whole"] == "植物"
    assert brace["topic"] == "植物"

    flow = apply_locked_topic_to_spec({"title": "old"}, "水循环", "flow_map")
    assert flow["title"] == "水循环"


def test_mind_map_validate_rejects_flat_children() -> None:
    """Hierarchy mode rejects main branches that have no nested children."""
    agent = MindMapAgent(model="qwen")
    flat = {
        "topic": "钢琴",
        "children": [
            {"id": "1", "text": "A"},
            {"id": "2", "text": "B"},
            {"id": "3", "text": "C"},
            {"id": "4", "text": "D"},
        ],
    }
    ok, msg = agent.validate_output(flat, enforce_hierarchy=True)
    assert ok is False
    assert "nested children" in msg


def test_mind_map_validate_accepts_nested_even_branch_count() -> None:
    """Accept four nested main branches with text children."""
    agent = MindMapAgent(model="qwen")
    nested = {
        "topic": "钢琴",
        "children": [
            {
                "id": "1",
                "text": "技巧",
                "children": [{"id": "1a", "text": "音阶"}],
            },
            {
                "id": "2",
                "text": "曲目",
                "children": [{"id": "2a", "text": "练习曲"}],
            },
            {
                "id": "3",
                "text": "理论",
                "children": [{"id": "3a", "text": "和声"}],
            },
            {
                "id": "4",
                "text": "表演",
                "children": [{"id": "4a", "text": "舞台"}],
            },
        ],
    }
    ok, msg = agent.validate_output(nested, enforce_hierarchy=True)
    assert ok is True
    assert msg.startswith("Valid")


def test_mind_map_validate_rejects_wrong_branch_count() -> None:
    """Hierarchy mode requires 4, 6, or 8 main branches."""
    agent = MindMapAgent(model="qwen")
    three = {
        "topic": "钢琴",
        "children": [
            {"id": "1", "text": "A", "children": [{"id": "1a", "text": "x"}]},
            {"id": "2", "text": "B", "children": [{"id": "2a", "text": "y"}]},
            {"id": "3", "text": "C", "children": [{"id": "3a", "text": "z"}]},
        ],
    }
    ok, msg = agent.validate_output(three, enforce_hierarchy=True)
    assert ok is False
    assert "4, 6, or 8" in msg
