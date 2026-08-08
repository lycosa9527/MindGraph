"""Tests for mind map node-explain facet prompts and billing wiring."""

from agents.mind_maps.node_explain import _build_facet_prompt, _normalize_facet
from services.redis.redis_activity_tracker import RedisActivityTracker
from utils.auth.thinking_coin_config import CANVAS_ASSIST_REQUEST_TYPES


def test_normalize_facet_accepts_known_values() -> None:
    """Known facet strings should round-trip unchanged."""
    assert _normalize_facet("meaning") == "meaning"
    assert _normalize_facet("conflict") == "conflict"
    assert _normalize_facet("questions") == "questions"


def test_normalize_facet_defaults_unknown_to_meaning() -> None:
    """Unknown facet values fall back to meaning."""
    assert _normalize_facet("") == "meaning"
    assert _normalize_facet("other") == "meaning"


def test_meaning_prompt_stays_on_topic_relationship() -> None:
    """Meaning facet should explain node-topic relation and avoid other panels."""
    prompt = _build_facet_prompt(
        facet="meaning",
        node_label="光合作用",
        topic="植物",
        diagram_type="mindmap",
        top_level_branches=["根", "茎", "叶"],
        ancestor_path=["叶"],
        sibling_branches=["呼吸作用"],
        child_branches=[],
        language="zh",
    )
    assert "光合作用" in prompt
    assert "中心主题：植物" in prompt
    assert "不要写认知冲突" in prompt
    assert "不要列问题" in prompt


def test_conflict_prompt_excludes_full_definition() -> None:
    """Conflict facet should focus on tension and avoid full definitions."""
    prompt = _build_facet_prompt(
        facet="conflict",
        node_label="Photosynthesis",
        topic="Plants",
        diagram_type="mindmap",
        top_level_branches=["Roots", "Leaves"],
        ancestor_path=["Leaves"],
        sibling_branches=["Respiration"],
        child_branches=[],
        language="en",
    )
    assert "Photosynthesis" in prompt
    assert "cognitive conflict" in prompt.lower() or "Cognitive conflicts" in prompt
    assert "Do not give a full definition" in prompt


def test_questions_prompt_asks_for_three_items() -> None:
    """Questions facet should request exactly three numbered inquiry prompts."""
    prompt = _build_facet_prompt(
        facet="questions",
        node_label="Photosynthesis",
        topic="Plants",
        diagram_type="mindmap",
        top_level_branches=["Roots"],
        ancestor_path=[],
        sibling_branches=[],
        child_branches=[],
        language="en",
    )
    assert "3 short" in prompt
    assert "1. 2. 3." in prompt


def test_mindmap_node_explain_is_canvas_assist_request_type() -> None:
    """Explain facets should bill as canvas-assist (not full diagram generation)."""
    assert "mindmap_node_explain" in CANVAS_ASSIST_REQUEST_TYPES


def test_mindmap_node_explain_live_activity_label_registered() -> None:
    """Redis live activity tracks explain opens; LLM text itself is not persisted."""
    assert "mindmap_node_explain" in RedisActivityTracker.ACTIVITY_TYPES
