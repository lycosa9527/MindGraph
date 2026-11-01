"""Draft seminar minutes with DashScope ``qwen3.8-flash``.

The room used to post the transcript into the MindMate chat stream. That
stream rejects messages longer than 5,000 characters, so 生成纪要 failed
before a model saw the seminar. This call is a one-shot JSON draft.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from models.common import LLMModel
from services.llm import llm_service

logger = logging.getLogger(__name__)

SEMINAR_MINUTES_MODEL = LLMModel.QWEN38_FLASH.value
SEMINAR_MINUTES_ENDPOINT = "/api/mindmate/seminar/{session_id}/minutes"
SEMINAR_MINUTES_REQUEST_TYPE = "mindmate"
_TRANSCRIPT_LIMIT = 48_000
_MAX_TOKENS = 4096


@dataclass(frozen=True)
class MinutesDraftInput:
    """Facts the minutes model may use. Empty lists stay empty."""

    zh: bool
    topic: str
    goals: list[str]
    speakers: str
    observers: str
    files: list[str]
    quotes: list[str]
    transcript: str


def _clip(text: str, limit: int) -> str:
    return text.strip()[:limit]


def _clip_lines(items: list[str], limit: int, item_limit: int) -> list[str]:
    kept: list[str] = []
    for item in items:
        text = _clip(item, item_limit)
        if not text:
            continue
        kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def build_minutes_prompt(draft: MinutesDraftInput) -> str:
    """User prompt. The model must answer with the minutes JSON only."""
    topic = _clip(draft.topic, 200)
    goals = _clip_lines(draft.goals, 12, 200)
    files = _clip_lines(draft.files, 30, 180)
    quotes = _clip_lines(draft.quotes, 3, 400)
    speakers = _clip(draft.speakers, 2000)
    observers = _clip(draft.observers, 2000)
    transcript = draft.transcript.strip()[-_TRANSCRIPT_LIMIT:]
    facts = [
        f"主题：{topic}" if topic else "",
        "教研目标：\n" + "\n".join(f"- {goal}" for goal in goals) if goals else "",
        f"发言人：{speakers}" if speakers else "",
        f"到场观摩：{observers}" if observers else "",
        "对话中出现的文件：\n" + "\n".join(f"- {name}" for name in files) if files else "",
        "已标精华：\n" + "\n".join(f"- {line}" for line in quotes) if quotes else "",
    ]
    fact_block = "\n".join(line for line in facts if line)
    instruction = (
        [
            "请根据研讨记录写一份教研纪要，只输出 JSON，不要 Markdown。",
            "键：goals, consensus, open, materials, tasks, quotes。",
            'goals 是数组，每项为 {"goal":"目标原文","status":"met|partial|open"}。'
            "status 只能是已回应 met、部分回应 partial、尚未讨论 open。",
            "其余键是字符串数组。consensus 写已经说定的判断。open 写尚未决定的分歧，不要替组里选边。",
            "materials 只写记录里真正用到的材料，以及它用来说明什么。tasks 写谁来做什么；没有说时间就不要写时间。",
            "quotes 最多 3 条，优先使用已标精华，格式「姓名：原话」。",
            "没有依据的决定不要写。空的数组用 []。",
        ]
        if draft.zh
        else [
            "Write seminar minutes as JSON only, with no Markdown.",
            "Keys: goals, consensus, open, materials, tasks, quotes.",
            'goals is an array of {"goal":"...","status":"met|partial|open"} using the goal text given above.',
            "The other keys are string arrays. consensus holds agreed points. "
            "open holds unresolved disagreements without picking a side.",
            "materials names only files actually used, and what they were used to show. "
            "tasks name who does what, and include a time only if one was stated.",
            'quotes has at most 3 lines, preferring the marked highlights, formatted as "Name: quote".',
            "Do not invent decisions. Use [] for an empty array.",
        ]
    )
    return "\n".join(instruction) + f"\n\n{fact_block}\n\n记录：\n{transcript}"


def _reply_text(raw: object) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list) and raw:
        return str(raw[0]).strip()
    return ""


async def draft_seminar_minutes(
    draft: MinutesDraftInput,
    *,
    user_id: int,
    organization_id: int | None,
) -> str:
    """Ask qwen3.8-flash for the minutes JSON. Empty output is a failure."""
    transcript = draft.transcript.strip()
    if not transcript:
        logger.info("[MindmateSeminarMinutes] draft skipped; empty transcript user=%s", user_id)
        raise ValueError("empty_transcript")
    raw = await llm_service.chat(
        prompt=build_minutes_prompt(draft),
        model=SEMINAR_MINUTES_MODEL,
        temperature=0.2,
        max_tokens=_MAX_TOKENS,
        use_knowledge_base=False,
        user_id=user_id,
        organization_id=organization_id,
        request_type=SEMINAR_MINUTES_REQUEST_TYPE,
        endpoint_path=SEMINAR_MINUTES_ENDPOINT,
        response_format={"type": "json_object"},
    )
    text = _reply_text(raw)
    if not text:
        logger.warning("[MindmateSeminarMinutes] draft empty user=%s org=%s", user_id, organization_id)
        raise ValueError("empty_reply")
    logger.info("[MindmateSeminarMinutes] draft ready user=%s chars=%s", user_id, len(text))
    return text
