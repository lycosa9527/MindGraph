"""Compatibility re-export — lesson planner lives in mind_classroom."""

from services.llm import llm_service
from services.mind_classroom.lesson_planner import (
    DEFAULT_PLANNER_MAX_TOKENS,
    DEFAULT_PLANNER_MODEL,
    develop_branch_first_seen_texts,
    normalize_lesson_plan_to_outline,
    parse_close_phase_json,
    parse_develop_phase_json,
    parse_lesson_plan_json,
    parse_open_phase_json,
    plan_lesson_from_outline,
    planner_max_tokens,
    planner_model_id,
    reorder_develop_batches_to_outline,
)

__all__ = [
    "DEFAULT_PLANNER_MAX_TOKENS",
    "DEFAULT_PLANNER_MODEL",
    "develop_branch_first_seen_texts",
    "normalize_lesson_plan_to_outline",
    "parse_close_phase_json",
    "parse_develop_phase_json",
    "parse_lesson_plan_json",
    "parse_open_phase_json",
    "plan_lesson_from_outline",
    "planner_max_tokens",
    "planner_model_id",
    "reorder_develop_batches_to_outline",
    "llm_service",
]
