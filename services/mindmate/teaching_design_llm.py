"""Optional LLM mapping when heading parse cannot fill the Word spec."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.llm import llm_service
from services.mindmate.teaching_design_models import (
    ActivityStage,
    TeachingDesignSpec,
    ThinkingPointRow,
)
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

_SYSTEM_PROMPT = (
    "你把教师教学设计正文映射到固定 JSON 字段。只使用原文已有内容，不要编造课例结构、板书、作业或素材。"
    "没有的字段用空字符串或空数组。只输出一个 JSON 对象。"
)

_USER_PROMPT = """把下面的教学设计映射为 JSON，字段如下：
title, grade, subject, textbook, period, school, teacher, summary,
content_analysis, learner_analysis, objectives, structure, board_design,
homework, materials,
thinking_points: [{{"category":"问题情境|认知冲突|思维可视化|变式运用","point":"","intent":""}}],
activities: [{{"title":"","teacher_actions":[""],"student_actions":[""],"intent":""}}]

正文：
{markdown}
"""


def merge_teaching_design_specs(
    base: TeachingDesignSpec,
    incoming: TeachingDesignSpec,
) -> TeachingDesignSpec:
    """Fill empty base fields from incoming; keep parsed rows when already present."""
    merged = TeachingDesignSpec(
        title=base.title or incoming.title,
        grade=base.grade or incoming.grade,
        subject=base.subject or incoming.subject,
        textbook=base.textbook or incoming.textbook,
        period=base.period or incoming.period,
        school=base.school or incoming.school,
        teacher=base.teacher or incoming.teacher,
        summary=base.summary or incoming.summary,
        content_analysis=base.content_analysis or incoming.content_analysis,
        learner_analysis=base.learner_analysis or incoming.learner_analysis,
        objectives=base.objectives or incoming.objectives,
        structure=base.structure or incoming.structure,
        board_design=base.board_design or incoming.board_design,
        homework=base.homework or incoming.homework,
        materials=base.materials or incoming.materials,
        thinking_source=base.thinking_source or incoming.thinking_source,
        activity_source=base.activity_source or incoming.activity_source,
        leftover=base.leftover or incoming.leftover,
        thinking_points=list(base.thinking_points or incoming.thinking_points),
        activities=list(base.activities or incoming.activities),
    )
    return merged


def spec_from_mapping(payload: dict[str, Any]) -> TeachingDesignSpec:
    """Build a spec from an LLM JSON object."""
    thinking_rows: list[ThinkingPointRow] = []
    raw_points = payload.get("thinking_points")
    if isinstance(raw_points, list):
        for item in raw_points:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "")).strip()
            point = str(item.get("point", "")).strip()
            if not category and not point:
                continue
            thinking_rows.append(
                ThinkingPointRow(
                    category=category,
                    point=point,
                    intent=str(item.get("intent", "")).strip(),
                )
            )
    activities: list[ActivityStage] = []
    raw_activities = payload.get("activities")
    if isinstance(raw_activities, list):
        for item in raw_activities:
            if not isinstance(item, dict):
                continue
            activities.append(
                ActivityStage(
                    title=str(item.get("title", "")).strip(),
                    teacher_actions=_string_list(item.get("teacher_actions")),
                    student_actions=_string_list(item.get("student_actions")),
                    intent=str(item.get("intent", "")).strip(),
                )
            )
    return TeachingDesignSpec(
        title=str(payload.get("title", "")).strip(),
        grade=str(payload.get("grade", "")).strip(),
        subject=str(payload.get("subject", "")).strip(),
        textbook=str(payload.get("textbook", "")).strip(),
        period=str(payload.get("period", "")).strip(),
        school=str(payload.get("school", "")).strip(),
        teacher=str(payload.get("teacher", "")).strip(),
        summary=str(payload.get("summary", "")).strip(),
        content_analysis=str(payload.get("content_analysis", "")).strip(),
        learner_analysis=str(payload.get("learner_analysis", "")).strip(),
        objectives=str(payload.get("objectives", "")).strip(),
        structure=str(payload.get("structure", "")).strip(),
        board_design=str(payload.get("board_design", "")).strip(),
        homework=str(payload.get("homework", "")).strip(),
        materials=str(payload.get("materials", "")).strip(),
        thinking_points=thinking_rows,
        activities=activities,
    )


def extract_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM reply that may wrap fences."""
    text = _JSON_FENCE_RE.sub("", (raw or "").strip()).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM reply is not a JSON object")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON is not an object")
    return parsed


async def fill_teaching_design_with_llm(
    markdown: str,
    *,
    user_id: int | None,
    organization_id: int | None,
) -> TeachingDesignSpec:
    """Map free markdown into the typed spec. Raises on empty or invalid JSON."""
    raw = await llm_service.chat(
        prompt=_USER_PROMPT.format(markdown=markdown[:12000]),
        system_message=_SYSTEM_PROMPT,
        model="qwen",
        temperature=0.2,
        max_tokens=8000,
        user_id=user_id,
        organization_id=organization_id,
        request_type="teaching_design_export",
        endpoint_path="/api/export_teaching_design_docx",
        use_knowledge_base=False,
        response_format={"type": "json_object"},
    )
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    text = str(raw).strip()
    if not text:
        raise ValueError("empty_llm_response")
    return spec_from_mapping(extract_json_object(text))


async def complete_teaching_design_spec(
    parsed: TeachingDesignSpec,
    markdown: str,
    *,
    user_id: int | None,
    organization_id: int | None,
    teacher_name: str | None,
) -> TeachingDesignSpec:
    """Parse-first, LLM for gaps, leftover 摘要 fallback, then teacher name."""
    spec = parsed
    if spec.needs_llm_fill():
        logger.info(
            "[TeachingDesignExport] llm_fill start user=%s org=%s markdown_chars=%s",
            user_id,
            organization_id,
            len(markdown),
        )
        try:
            filled = await fill_teaching_design_with_llm(
                markdown,
                user_id=user_id,
                organization_id=organization_id,
            )
            spec = merge_teaching_design_specs(spec, filled)
            logger.info(
                "[TeachingDesignExport] llm_fill ok user=%s prose=%s thinking=%s activities=%s",
                user_id,
                spec.filled_prose_count(),
                len(spec.thinking_points),
                len(spec.activities),
            )
        except LLM_PIPELINE_ERRORS:
            logger.warning(
                "[TeachingDesignExport] llm_fill failed user=%s",
                user_id,
                exc_info=True,
            )
    else:
        logger.info(
            "[TeachingDesignExport] parse_only user=%s prose=%s thinking=%s activities=%s",
            user_id,
            spec.filled_prose_count(),
            len(spec.thinking_points),
            len(spec.activities),
        )
    if not spec.summary.strip():
        spec.summary = spec.leftover.strip() or markdown.strip()
        logger.info(
            "[TeachingDesignExport] summary_fallback user=%s leftover=%s",
            user_id,
            bool(spec.leftover.strip()),
        )
    if teacher_name and not spec.teacher.strip():
        spec.teacher = teacher_name.strip()
    return spec


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
