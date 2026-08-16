"""Compatibility re-export — lesson/Wan prompts live in mind_classroom."""

from services.mind_classroom.prompts import (
    LESSON_PLANNER_REPAIR_USER,
    LESSON_PLANNER_SYSTEM,
    WAN_IMAGE_SHELL,
    build_branch_planner_message,
    build_close_planner_message,
    build_lesson_planner_user_message,
    build_open_planner_message,
)

__all__ = [
    "LESSON_PLANNER_SYSTEM",
    "LESSON_PLANNER_REPAIR_USER",
    "WAN_IMAGE_SHELL",
    "build_lesson_planner_user_message",
    "build_open_planner_message",
    "build_branch_planner_message",
    "build_close_planner_message",
]
