"""Tests for mind map node-explain facet prompts and billing wiring."""

from unittest.mock import MagicMock, patch

from agents.mind_maps.node_explain_activity import (
    ExplainActivityContext,
    ExplainStreamStats,
    is_internal_explain_event,
    schedule_explain_completion_activity,
)
from agents.mind_maps.node_explain_prompts import (
    RESEARCH_IMAGE_TOOLS,
    RESEARCH_TOOLS,
    build_facet_prompt,
    build_research_image_prompt,
    build_research_meaning_prompt,
    max_tokens_for_audience,
    normalize_facet,
    style_band_for_level,
)
from models.requests.requests_thinking import MindMapNodeExplainRequest
from services.admin.school_feature_usage_catalog import resolve_feature_module
from services.admin.user_usage_activity import VALID_ACTIVITY_ACTIONS
from services.redis.redis_activity_tracker import RedisActivityTracker
from utils.auth.thinking_coin_config import CANVAS_ASSIST_REQUEST_TYPES

_PROMPT_KWARGS = {
    "node_label": "光合作用",
    "topic": "植物",
    "diagram_type": "mindmap",
    "top_level_branches": ["根", "茎", "叶"],
    "ancestor_path": ["叶"],
    "sibling_branches": ["呼吸作用"],
    "child_branches": [],
}


def test_normalize_facet_accepts_known_values() -> None:
    """Known facet strings should round-trip unchanged."""
    assert normalize_facet("meaning") == "meaning"
    assert normalize_facet("conflict") == "conflict"
    assert normalize_facet("questions") == "questions"


def test_normalize_facet_defaults_unknown_to_meaning() -> None:
    """Unknown facet values fall back to meaning."""
    assert normalize_facet("") == "meaning"
    assert normalize_facet("other") == "meaning"


def test_style_bands_split_kid_school_and_professional() -> None:
    """Primary stays kid-friendly; audits use the professional band."""
    assert style_band_for_level("primary") == "kid"
    assert style_band_for_level("junior") == "school"
    assert style_band_for_level("senior") == "school"
    assert style_band_for_level("university") == "pro"
    assert style_band_for_level("adult") == "pro"
    assert style_band_for_level("expert") == "pro"
    assert style_band_for_level("general") == "general"
    assert style_band_for_level("unknown") == "general"


def test_token_budget_grows_for_professional_levels() -> None:
    """Kid glosses stay short; expert / audit glosses need more tokens."""
    assert max_tokens_for_audience("primary") == 512
    assert max_tokens_for_audience("expert") == 768
    assert max_tokens_for_audience("expert") > max_tokens_for_audience("primary")


def test_general_meaning_prompt_is_neutral() -> None:
    """Unset 专业程度 must not force a children's apple gloss."""
    prompt = build_facet_prompt(facet="meaning", language="zh", **_PROMPT_KWARGS)
    assert "光合作用" in prompt
    assert "中心主题：植物" in prompt
    assert "【专业程度】" in prompt
    assert "专业程度：通用" in prompt
    assert "不要故意小学化" in prompt
    assert "不少于 250 字" in prompt
    assert "250–400 字" in prompt
    assert "40–60" not in prompt
    assert "一两句" not in prompt
    assert "短释义" not in prompt
    assert "小朋友" not in prompt
    assert "苹果是长在树上的红色水果" not in prompt


def test_primary_meaning_prompt_uses_kid_voice() -> None:
    """小学 专业程度 keeps the everyday children's gloss."""
    prompt = build_facet_prompt(
        facet="meaning",
        language="zh",
        audience_level="primary",
        **_PROMPT_KWARGS,
    )
    assert "日常口语" in prompt
    assert "小朋友" in prompt
    assert "苹果是长在树上的红色水果" in prompt
    assert "不少于 250 字" in prompt
    assert "250–400 字" in prompt
    assert "专业程度：小学" in prompt
    assert "禁止术语" in prompt


def test_expert_meaning_prompt_is_audit_ready() -> None:
    """专家 专业程度 asks for a peer / audit gloss, not a kid story."""
    prompt = build_facet_prompt(
        facet="meaning",
        language="zh",
        audience_level="expert",
        **_PROMPT_KWARGS,
    )
    assert "领域术语" in prompt
    assert "可审阅" in prompt
    assert "禁止科普开场" in prompt
    assert "专业程度：专家" in prompt
    assert "小朋友" not in prompt
    assert "苹果是长在树上的红色水果" not in prompt


def test_english_primary_meaning_prompt_keeps_apple_example() -> None:
    """English primary still uses the short everyday apple gloss."""
    prompt = build_facet_prompt(
        facet="meaning",
        node_label="Apple",
        topic="Fruit",
        diagram_type="mindmap",
        top_level_branches=["Citrus", "Berries"],
        ancestor_path=[],
        sibling_branches=["Pear"],
        child_branches=[],
        language="en",
        audience_level="primary",
    )
    assert "Apple" in prompt
    assert "160–260 words" in prompt
    assert "red fruit that grows on trees" in prompt
    assert "Expertise: primary school" in prompt


def test_english_expert_meaning_prompt_asks_for_audit_gloss() -> None:
    """English expert meaning should be dense and audit-ready."""
    prompt = build_facet_prompt(
        facet="meaning",
        node_label="Photosynthesis",
        topic="Plants",
        diagram_type="mindmap",
        top_level_branches=["Roots", "Leaves"],
        ancestor_path=["Leaves"],
        sibling_branches=["Respiration"],
        child_branches=[],
        language="en",
        audience_level="expert",
    )
    assert "audit-ready" in prompt
    assert "Domain terminology" in prompt
    assert "Expertise: expert peer" in prompt
    assert "red fruit that grows on trees" not in prompt


def test_generation_instructions_are_appended() -> None:
    """Frontend 专业程度 templates still land on the prompt."""
    prompt = build_facet_prompt(
        facet="meaning",
        language="zh",
        audience_level="primary",
        generation_instructions="请按「小学」专业程度生成内容。\n用语：只用日常具体词。",
        **_PROMPT_KWARGS,
    )
    assert "请按「小学」专业程度生成内容。" in prompt
    assert "只用日常具体词" in prompt


def test_conflict_prompt_excludes_full_definition() -> None:
    """Conflict facet should focus on tension and avoid full definitions."""
    prompt = build_facet_prompt(
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
    prompt = build_facet_prompt(
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


def test_explain_request_accepts_audience_level() -> None:
    """Explain API should take a first-class 专业程度 id."""
    req = MindMapNodeExplainRequest.model_validate(
        {
            "session_id": "explain01",
            "node_id": "n1",
            "node_label": "光合作用",
            "audience_level": "expert",
        }
    )
    assert req.audience_level == "expert"


def test_explain_request_unknown_audience_falls_back_to_general() -> None:
    """Unknown 专业程度 ids must not break the stream."""
    req = MindMapNodeExplainRequest.model_validate(
        {
            "session_id": "explain01",
            "node_id": "n1",
            "node_label": "光合作用",
            "audience_level": "phd",
        }
    )
    assert req.audience_level == "general"


def test_research_meaning_prompt_writes_from_search() -> None:
    """Meaning research writes from search; page fetch is not advertised."""
    prompt = build_research_meaning_prompt(language="zh", **_PROMPT_KWARGS)
    assert "【联网研究】" in prompt
    assert "web_search" in prompt
    assert "web_search_image" not in prompt
    assert "web_extractor" not in prompt
    assert "搜索一返回就根据标题和摘要写释义" in prompt
    assert "不少于 250 字" in prompt
    assert "250–400 字" in prompt
    assert "40–60" not in prompt
    assert "一两句" not in prompt
    assert "短释义" not in prompt
    assert "不要打开网页" in prompt
    assert "[1][2]" in prompt
    assert RESEARCH_TOOLS == ("web_search",)
    assert RESEARCH_IMAGE_TOOLS == ("web_search_image",)
    image_prompt = build_research_image_prompt(
        node_label="光合作用",
        topic="植物",
        language="zh",
    )
    assert "web_search_image" in image_prompt
    assert "不要写释义" in image_prompt
    assert "约 24 张配图" in image_prompt


def test_mindmap_node_explain_is_canvas_assist_request_type() -> None:
    """Explain facets should bill as canvas-assist (not full diagram generation)."""
    assert "mindmap_node_explain" in CANVAS_ASSIST_REQUEST_TYPES


def test_mindmap_node_explain_live_activity_label_registered() -> None:
    """Redis live activity tracks explain opens; LLM text itself is not persisted."""
    assert "mindmap_node_explain" in RedisActivityTracker.ACTIVITY_TYPES


def test_mindmap_node_explain_usage_action_is_registered() -> None:
    """Completion writes a usage-timeline row with token counts."""
    assert "mindmap_node_explain" in VALID_ACTIVITY_ACTIONS
    assert resolve_feature_module("mindmap_node_explain", None, "mindgraph") == "canvas"


def test_explain_stream_stats_count_related_activities_and_tokens() -> None:
    """Search, sources, images, and write/image token lanes fold into one total."""
    stats = ExplainStreamStats()
    stats.observe({"event": "status", "phase": "searching", "query": "光合作用"})
    stats.observe(
        {
            "event": "search_source",
            "query": "光合作用",
            "sources": [{"url": "https://a.example"}, {"url": "https://b.example"}],
        }
    )
    stats.observe({"event": "image", "images": [{"url": "https://img.example/1.jpg"}]})
    stats.observe(
        {
            "event": "usage",
            "lane": "write",
            "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
        }
    )
    stats.observe(
        {
            "event": "usage",
            "lane": "image",
            "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
        }
    )
    assert stats.searches == 1
    assert stats.sources == 2
    assert stats.images == 1
    assert stats.queries == ["光合作用"]
    assert stats.write_tokens == 140
    assert stats.image_tokens == 30
    assert stats.total_tokens == 170
    assert is_internal_explain_event("usage")
    assert not is_internal_explain_event("token")


def test_explain_completion_activity_includes_token_counts() -> None:
    """Tracker + usage timeline receive search/image counts and billed tokens."""
    user = MagicMock()
    user.id = 9
    stats = ExplainStreamStats()
    stats.observe({"event": "status", "phase": "searching", "query": "光合作用"})
    stats.observe(
        {
            "event": "usage",
            "lane": "write",
            "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
        }
    )
    ctx = ExplainActivityContext(
        user=user,
        request=None,
        diagram_type="mindmap",
        diagram_id="11111111-1111-1111-1111-111111111111",
        session_id="explain01",
        facet="meaning",
        node_label="光合作用",
        topic="植物",
    )
    with patch(
        "agents.mind_maps.node_explain_activity.schedule_module_activity",
    ) as scheduled:
        schedule_explain_completion_activity(ctx, stats, success=True)

    kwargs = scheduled.call_args.kwargs
    assert kwargs["redis_activity_type"] == "mindmap_node_explain"
    assert kwargs["usage_action"] == "mindmap_node_explain"
    assert kwargs["persist_usage"] is True
    assert kwargs["total_tokens"] == 20
    assert kwargs["details"]["searches"] == 1
    assert kwargs["details"]["write_tokens"] == 20
    assert kwargs["details"]["queries"] == "光合作用"
