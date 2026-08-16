"""Final classroom prompts must be assembled from the four launch axes."""

from __future__ import annotations

from itertools import product

from services.mind_classroom.prompts.audience_prompts import AUDIENCE_LEVEL_IDS
from services.mind_classroom.prompts.canvas_tour_prompts import (
    CANVAS_TOUR_SYSTEM_SKELETON,
    build_canvas_tour_system_message,
    build_canvas_tour_user_message,
)
from services.mind_classroom.prompts.lesson_planner_prompts import (
    build_lesson_planner_system_message,
)
from services.mind_classroom.prompts.mastery_prompts import MASTERY_IDS
from services.mind_classroom.prompts.tone_prompts import TONE_IDS
from services.mind_classroom.prompts.tour_scope_prompts import (
    TOUR_SCOPE_IDS,
    normalize_tour_scope,
    tour_scope_brief,
    tour_scope_label,
)

# Same ids as frontend/src/config/mindClassroom.ts + aiContentLevels.ts
_UI_MASTERY = ("first_look", "review", "teach")
_UI_TOUR_SCOPE = ("main_branch", "each_node")
_UI_TONE = (
    "classroom",
    "story",
    "dialogue",
    "socratic",
    "fast",
    "close_read",
    "examples",
    "exam_outline",
)
_UI_AUDIENCE = ("general", "primary", "junior", "senior", "university", "adult", "expert")

_AUDIENCE_MARK = {
    "general": "专业程度：通用",
    "primary": "专业程度：小学",
    "junior": "专业程度：初中",
    "senior": "专业程度：高中",
    "university": "专业程度：大学",
    "adult": "专业程度：成人",
    "expert": "专业程度：专家",
}
_MASTERY_MARK = {
    "first_look": "第一次看",
    "review": "已经看过",
    "teach": "教别人",
}
_SCOPE_MARK = {
    "main_branch": "巡讲粒度：按主分支",
    "each_node": "巡讲粒度：逐个节点",
}
_TONE_MARK = {
    "classroom": "【课堂】",
    "story": "【讲故事】",
    "dialogue": "【对话追问】",
    "socratic": "【苏格拉底】",
    "fast": "【速讲】",
    "close_read": "【精读】",
    "examples": "【举例丰富】",
    "exam_outline": "【考点提纲】",
}


def test_normalize_tour_scope_defaults_to_main_branch() -> None:
    """Unknown 巡讲粒度 falls back to main branches."""
    assert normalize_tour_scope("") == "main_branch"
    assert normalize_tour_scope("deep") == "main_branch"
    assert normalize_tour_scope("each_node") == "each_node"


def test_tour_scope_briefs_differ() -> None:
    """Main-branch and each-node contracts must not collapse."""
    main = tour_scope_brief("main_branch", "zh")
    deep = tour_scope_brief("each_node", "zh")
    assert tour_scope_label("main_branch", "zh") == "按主分支"
    assert tour_scope_label("each_node", "zh") == "逐个节点"
    assert "子点不拆步" in main
    assert "stop=leaf" in deep
    assert main != deep


def test_canvas_system_is_built_from_selection() -> None:
    """System prompt must not stay first-look; it follows the four selected briefs."""
    review_fast = build_canvas_tour_system_message(
        {
            "mastery": "review",
            "tone": "fast",
            "tour_scope": "each_node",
            "audience_level": "expert",
            "language": "zh",
        }
    )
    first_story = build_canvas_tour_system_message(
        {
            "mastery": "first_look",
            "tone": "story",
            "tour_scope": "main_branch",
            "audience_level": "primary",
            "language": "zh",
        }
    )
    assert "用户正在初识一张新导图" not in CANVAS_TOUR_SYSTEM_SKELETON
    assert "用户正在初识一张新导图" not in review_fast
    assert "本场选择" in review_fast
    assert "复习巩固" in review_fast
    assert "【速讲】" in review_fast
    assert "逐个节点" in review_fast
    assert "专家" in review_fast
    assert "第一次看" in first_story
    assert "【讲故事】" in first_story
    assert "小学" in first_story
    assert review_fast != first_story


def test_slide_system_follows_selection_without_tour_scope() -> None:
    """Slide planner has no 巡讲粒度; audience / mastery / tone still assemble."""
    teach = build_lesson_planner_system_message(
        {"mastery": "teach", "tone": "exam_outline", "audience_level": "senior", "language": "zh"}
    )
    assert "资深 K12" not in teach
    assert "备课讲授" in teach
    assert "【考点提纲】" in teach
    assert "高中" in teach
    assert "巡讲粒度" not in teach


def test_canvas_user_message_always_has_four_briefs() -> None:
    """Review + each_node still carries tour_scope_brief, not first-look-only extras."""
    text = build_canvas_tour_user_message(
        [{"id": "topic", "text": "苏州", "kind": "topic"}],
        settings={
            "mastery": "review",
            "tone": "socratic",
            "tour_scope": "each_node",
            "audience_level": "adult",
            "language": "zh",
        },
        max_steps=12,
    )
    assert "mastery_brief" in text
    assert "audience_brief" in text
    assert "tone_brief" in text
    assert "tour_scope_brief" in text
    assert "【苏格拉底】" in text
    assert "branch_tutor_brief" not in text
    assert "overview_tutor_brief" not in text


def test_backend_ids_match_launch_ui() -> None:
    """Every launch-modal / toolbar option has a backend brief id."""
    assert MASTERY_IDS == frozenset(_UI_MASTERY)
    assert TOUR_SCOPE_IDS == frozenset(_UI_TOUR_SCOPE)
    assert TONE_IDS == frozenset(_UI_TONE)
    assert AUDIENCE_LEVEL_IDS == frozenset(_UI_AUDIENCE)


def test_every_canvas_combo_embeds_the_four_selected_briefs() -> None:
    """7×3×2×8 canvas selections each appear in both system and user prompts."""
    nodes = [{"id": "topic", "text": "苏州", "kind": "topic"}]
    for audience, mastery, scope, tone in product(_UI_AUDIENCE, _UI_MASTERY, _UI_TOUR_SCOPE, _UI_TONE):
        settings = {
            "audience_level": audience,
            "mastery": mastery,
            "tour_scope": scope,
            "tone": tone,
            "language": "zh",
        }
        system = build_canvas_tour_system_message(settings)
        user = build_canvas_tour_user_message(nodes, settings=settings, max_steps=12)
        for text in (system, user):
            assert _AUDIENCE_MARK[audience] in text
            assert _MASTERY_MARK[mastery] in text
            assert _SCOPE_MARK[scope] in text
            assert _TONE_MARK[tone] in text


def test_every_slide_combo_embeds_audience_mastery_tone() -> None:
    """7×3×8 slide selections assemble; 巡讲粒度 stays out."""
    for audience, mastery, tone in product(_UI_AUDIENCE, _UI_MASTERY, _UI_TONE):
        system = build_lesson_planner_system_message(
            {
                "audience_level": audience,
                "mastery": mastery,
                "tone": tone,
                "language": "zh",
            }
        )
        assert _AUDIENCE_MARK[audience] in system
        assert _MASTERY_MARK[mastery] in system
        assert _TONE_MARK[tone] in system
        assert "巡讲粒度" not in system
