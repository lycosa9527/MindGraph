"""Mind Classroom prompt set A (lesson) and set B (Wan image shell)."""

from services.mind_classroom.prompts.audience_prompts import (
    audience_brief,
    normalize_audience_level,
)
from services.mind_classroom.prompts.lesson_planner_prompts import (
    LESSON_PLANNER_REPAIR_USER,
    LESSON_PLANNER_SYSTEM,
    build_branch_planner_message,
    build_close_planner_message,
    build_lesson_planner_system_message,
    build_lesson_planner_user_message,
    build_open_planner_message,
)
from services.mind_classroom.prompts.mastery_prompts import (
    build_axis_contract_block,
    classroom_pref_fields,
    mastery_brief,
    normalize_mastery,
)
from services.mind_classroom.prompts.tone_prompts import normalize_tone, tone_brief
from services.mind_classroom.prompts.tour_scope_prompts import (
    normalize_tour_scope,
    tour_scope_brief,
)
from services.mind_classroom.prompts.wan_image_shell import WAN_IMAGE_SHELL

__all__ = [
    "LESSON_PLANNER_SYSTEM",
    "LESSON_PLANNER_REPAIR_USER",
    "WAN_IMAGE_SHELL",
    "build_lesson_planner_system_message",
    "build_lesson_planner_user_message",
    "build_open_planner_message",
    "build_branch_planner_message",
    "build_close_planner_message",
    "audience_brief",
    "build_axis_contract_block",
    "classroom_pref_fields",
    "mastery_brief",
    "normalize_audience_level",
    "normalize_mastery",
    "normalize_tone",
    "normalize_tour_scope",
    "tone_brief",
    "tour_scope_brief",
]
