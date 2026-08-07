"""ZhiHui prompt set A (lesson) and set B (Wan image shell)."""

from services.zhihui.prompts.lesson_planner_prompts import (
    LESSON_PLANNER_REPAIR_USER,
    LESSON_PLANNER_SYSTEM,
    build_lesson_planner_user_message,
)
from services.zhihui.prompts.wan_image_shell import WAN_IMAGE_SHELL

__all__ = [
    "LESSON_PLANNER_SYSTEM",
    "LESSON_PLANNER_REPAIR_USER",
    "WAN_IMAGE_SHELL",
    "build_lesson_planner_user_message",
]
