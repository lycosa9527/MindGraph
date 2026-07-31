"""
Task-type to model/prompt routing for Maite learning.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass

from services.maite.prompts.registry import get_prompt_registry

_VISION_TASKS = frozenset({"ocr_extract"})


@dataclass(frozen=True, slots=True)
class ModelRouteContext:
    """Resolved prompt and model for a Maite LLM call."""

    prompt_id: str
    model: str
    requires_vision: bool


def route(task_type: str, *, has_image: bool = False) -> ModelRouteContext:
    """Map a Maite task type to prompt id and model hint.

    Vision is reserved for OCR extraction. Downstream diagnosis/remedy/variant
    tasks stay on the text model even when the original problem had an image.
    """
    _ = has_image  # call-site clarity; OCR vision uses task_type only
    registry = get_prompt_registry()
    template = registry.get_by_task_type(task_type)
    requires_vision = task_type in _VISION_TASKS
    model = template.model_hint
    if requires_vision and "vl" not in model:
        model = "qwen-vl-max"
    return ModelRouteContext(
        prompt_id=template.id,
        model=model,
        requires_vision=requires_vision,
    )
