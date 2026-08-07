"""Prompt set A — call qwen3.7-plus to produce structural lesson JSON."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from config.settings import config
from services.llm import llm_service
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from services.zhihui.outline import MindMapOutline
from services.zhihui.prompts.lesson_planner_prompts import (
    LESSON_PLANNER_REPAIR_USER,
    LESSON_PLANNER_SYSTEM,
    build_lesson_planner_user_message,
)

logger = logging.getLogger(__name__)

DEFAULT_PLANNER_MODEL = "qwen3.7-plus"


def planner_model_id() -> str:
    """Resolve lesson planner model from env/settings."""
    raw = getattr(config, "ZHIHUI_LESSON_PLANNER_MODEL", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return DEFAULT_PLANNER_MODEL


def _strip_code_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()


def parse_lesson_plan_json(raw: str) -> dict[str, Any]:
    """Parse and lightly validate planner JSON."""
    cleaned = _strip_code_fence(raw)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Lesson plan root must be an object")
    batches = data.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("Lesson plan missing batches")
    has_frame = False
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        frames = batch.get("frames")
        if isinstance(frames, list) and any(isinstance(frame, dict) for frame in frames):
            has_frame = True
            break
    if not has_frame:
        raise ValueError("Lesson plan has no frames")
    if not str(data.get("style_seed") or "").strip():
        data["style_seed"] = "清新教育插画，柔和配色，统一扁平矢量风格"
    return data


async def plan_lesson_from_outline(
    outline: MindMapOutline,
    *,
    language: str = "zh",
    diagram_title: str = "",
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """
    Run qwen3.7-plus lesson planner.

    Returns (plan_dict, usage_data).
    """
    model = planner_model_id()
    user_message = build_lesson_planner_user_message(
        outline.to_planner_payload(),
        language=language,
        diagram_title=diagram_title or outline.topic,
    )
    usage: Optional[dict[str, Any]] = None
    try:
        response, usage = await llm_service.chat_with_usage(
            prompt=user_message,
            model=model,
            system_message=LESSON_PLANNER_SYSTEM,
            max_tokens=2500,
            temperature=0.4,
            user_id=user_id,
            organization_id=organization_id,
        )
        return parse_lesson_plan_json(response or ""), usage
    except (json.JSONDecodeError, ValueError, TypeError) as first_exc:
        logger.warning("[ZhiHui] Lesson plan parse failed, retrying: %s", first_exc)
        try:
            repair_prompt = f"{user_message}\n\n{LESSON_PLANNER_REPAIR_USER}"
            response, usage = await llm_service.chat_with_usage(
                prompt=repair_prompt,
                model=model,
                system_message=LESSON_PLANNER_SYSTEM,
                max_tokens=2500,
                temperature=0.2,
                user_id=user_id,
                organization_id=organization_id,
            )
            return parse_lesson_plan_json(response or ""), usage
        except (json.JSONDecodeError, ValueError, TypeError, *BACKGROUND_INFRA_ERRORS) as exc:
            raise ValueError(f"Lesson planner failed: {exc}") from exc
    except BACKGROUND_INFRA_ERRORS as exc:
        raise ValueError(f"Lesson planner failed: {exc}") from exc
