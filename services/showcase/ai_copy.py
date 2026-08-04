"""
Showcase teaching-design AI copy: extract document text then draft case fields.

Uses DashScope ``qwen3.7-flash`` with an education-focused prompt (思维发展型课堂).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, Dict, Optional

from services.knowledge.document_processor import get_document_processor
from services.llm import llm_service
from services.utils.error_types import JSON_PARSE_ERRORS, LLM_PIPELINE_ERRORS

# Canonical output keys → accepted aliases in model JSON.
# teaching_reflection is intentionally omitted: teachers fill it manually.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "description": ("description", "教学设计简介", "intro"),
    "design_highlights": (
        "design_highlights",
        "designHighlights",
        "设计亮点",
        "highlights",
    ),
}

logger = logging.getLogger(__name__)

SHOWCASE_AI_COPY_MODEL = "qwen3.7-flash"
SHOWCASE_AI_COPY_MAX_INPUT_CHARS = 32000
SHOWCASE_AI_COPY_MAX_FIELD_CHARS = 1200
# Per-field target (~200) × 2 fields ≈ 400 字 total.
SHOWCASE_AI_COPY_TARGET_CHARS_PER_FIELD = 200
SHOWCASE_AI_COPY_TARGET_CHARS_TOTAL = 400

_SYSTEM_PROMPT_ZH = """\
你是面向中小学教师的思维发展型课堂教研助手（MindGraph 案例广场）。用户会提供一份教学设计\
（或课件）文档正文，请据此撰写可直接发布的中文文案。平台强调「思维可视化 + 思维策略」，\
文案必须写出具体图示与思维类型，不能只写空泛目标。

读者是忙碌的中小学老师：用语要口语化、好读、好懂，减轻阅读负担。
- 多用短句和日常教研说法，少用论文腔、翻译腔和堆叠术语。
- 尽量少用或改写：脚手架、元认知、概念变式、过程性变式、认知负荷、显性化、\
建构、进阶、嵌入、嵌套、任务群、素养落地等偏学术说法；改成老师一听就懂的话\
（如：搭梯子、回头看自己的想法、换一种问法、负担太大、说清楚、自己想明白）。
- 图示名称（气泡图、双气泡图、流程图等）和常见思维说法（比较、因果、批判性思考）可保留，\
但要用「谁在什么环节用它做什么」说清楚，不要只甩术语。
- 直接写内容，勿提及 AI、模型、文档提取、Markdown 或本提示本身。

每个字段必须尽量落到文档中的真实设计，并点明：
1) 用了哪些图示/思维工具（如：圆圈图、气泡图、双气泡图、树形图、括号图、流程图、\
复流程图、桥形图、思维导图、结构图、PMI 等；文档没写的不要编）；
2) 主要练什么思维（如：观察归类、比较异同、找因果关系、按顺序梳理、打比方迁移、\
质疑证据、多角度看问题、课后复盘等）；
3) 用在哪个环节、帮助学生解决什么困难。

输出要求：
- 仅输出一个 JSON 对象（不要代码围栏、不要额外说明）。
- 字段仅两项：description（教学设计简介）、design_highlights（设计亮点）。\
不要输出教学反思或其他字段（教学反思由教师本人填写）。
- 每个字段写成一整段连贯中文（完整句子），不要分条、不要项目符号、不要用换行罗列；\
在段落里自然写清「图示/工具 + 思维类型 + 作用」。
- 字数硬性目标：教学设计简介、设计亮点各约 200 字（建议 190–210 字），\
两字段合计约 400 字；不要明显偏短，也不要某一字段独长。
- 紧扣学科、年级与文档内容；文档未写明的图示或活动不要虚构。"""

_USER_PROMPT_TEMPLATE_ZH = """\
【案例元信息】
标题：{title}
学科：{subject}
年级：{grade}

【教学设计文档正文】
{document_text}

请输出 JSON：仅 description 与 design_highlights，各约 200 字、合计约 400 字；\
每字段一整段完整句子；写清图示与思维，但用语要通俗、给中小学老师减负；\
勿分条、勿论文腔；勿输出教学反思。\
{{"description":"...","design_highlights":"..."}}"""


def strip_code_fence(raw: str) -> str:
    """Remove optional markdown code fences around model output."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_json_object(raw: str) -> Dict[str, Any]:
    """Parse a JSON object from model output, tolerating fences / noise."""
    text = strip_code_fence(raw)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except JSON_PARSE_ERRORS:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("not_a_dict")
    return parsed


def _clean_field(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # Prefer one paragraph per field: collapse bullets / hard line breaks.
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*\n+\s*", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text[:SHOWCASE_AI_COPY_MAX_FIELD_CHARS]


def normalize_ai_copy_fields(parsed: Dict[str, Any]) -> Dict[str, str]:
    """Normalize LLM JSON into showcase AI fields (reflection left for teachers)."""
    description = _clean_field(parsed.get("description") or parsed.get("教学设计简介") or parsed.get("intro"))
    highlights = _clean_field(
        parsed.get("design_highlights")
        or parsed.get("designHighlights")
        or parsed.get("设计亮点")
        or parsed.get("highlights")
    )
    if not description and not highlights:
        raise ValueError("empty_ai_copy_fields")
    return {
        "description": description,
        "design_highlights": highlights,
        # Kept for API shape; AI no longer drafts teaching reflection.
        "teaching_reflection": "",
    }


def _decode_json_string_prefix(raw: str) -> str:
    """Decode a JSON string body that may still be incomplete (no closing quote)."""
    out: list[str] = []
    index = 0
    length = len(raw)
    while index < length:
        char = raw[index]
        if char == "\\":
            if index + 1 >= length:
                break
            nxt = raw[index + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "r":
                out.append("\r")
            elif nxt == "t":
                out.append("\t")
            elif nxt in {'"', "\\", "/"}:
                out.append(nxt)
            elif nxt == "u" and index + 5 < length:
                hex_part = raw[index + 2 : index + 6]
                if re.fullmatch(r"[0-9a-fA-F]{4}", hex_part):
                    out.append(chr(int(hex_part, 16)))
                    index += 6
                    continue
                break
            else:
                break
            index += 2
            continue
        if char == '"':
            break
        out.append(char)
        index += 1
    return "".join(out)


def _extract_json_string_after_key(buffer: str, key: str) -> Optional[str]:
    """Return decoded string value for ``key`` from a partial JSON buffer."""
    pattern = re.compile(
        rf'"{re.escape(key)}"\s*:\s*"',
        flags=re.DOTALL,
    )
    match = pattern.search(buffer)
    if match is None:
        return None
    return _decode_json_string_prefix(buffer[match.end() :])


def extract_partial_json_string_fields(
    buffer: str,
    field_aliases: dict[str, tuple[str, ...]],
) -> Dict[str, str]:
    """
    Extract string fields from an incomplete JSON stream buffer.

    Returns only keys that have started (opening quote seen). Values are lightly
    trimmed; full normalize helpers run on the completed response.
    """
    text = strip_code_fence(buffer)
    result: Dict[str, str] = {}
    for canonical, aliases in field_aliases.items():
        value: Optional[str] = None
        for alias in aliases:
            value = _extract_json_string_after_key(text, alias)
            if value is not None:
                break
        if value is None:
            continue
        trimmed = value.strip()
        if trimmed:
            result[canonical] = trimmed[:SHOWCASE_AI_COPY_MAX_FIELD_CHARS]
    return result


def extract_partial_ai_copy_fields(buffer: str) -> Dict[str, str]:
    """
    Extract teaching-copy string fields from an incomplete JSON stream buffer.

    Returns only keys that have started (opening quote seen). Values are lightly
    trimmed; full ``normalize_ai_copy_fields`` runs on the completed response.
    """
    return extract_partial_json_string_fields(buffer, _FIELD_ALIASES)


def clean_ai_copy_field(value: Any) -> str:
    """Public wrapper for field cleanup used by sibling AI-copy modules."""
    return _clean_field(value)


def _build_teaching_copy_user_prompt(
    *,
    document_text: str,
    title: str,
    subject: str,
    grade: str,
) -> str:
    return _USER_PROMPT_TEMPLATE_ZH.format(
        title=title.strip() or "未命名案例",
        subject=subject.strip() or "未指定",
        grade=grade.strip() or "未指定",
        document_text=document_text.strip(),
    )


def extract_document_text(file_path: str) -> str:
    """Extract plain text from a teaching-design upload (.pdf/.doc/.docx/.pptx)."""
    processor = get_document_processor()
    file_type = processor.get_file_type(file_path)
    if not processor.is_supported(file_type):
        raise ValueError(f"unsupported_file_type:{file_type}")
    text = processor.extract_text(file_path, file_type)
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("no_text_extracted")
    if len(cleaned) > SHOWCASE_AI_COPY_MAX_INPUT_CHARS:
        cleaned = cleaned[:SHOWCASE_AI_COPY_MAX_INPUT_CHARS]
    return cleaned


async def generate_teaching_design_copy(
    *,
    document_text: str,
    title: str,
    subject: str,
    grade: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    endpoint_path: str,
) -> Dict[str, str]:
    """Call qwen3.7-flash and return intro/highlights (reflection left empty)."""
    user_prompt = _build_teaching_copy_user_prompt(
        document_text=document_text,
        title=title,
        subject=subject,
        grade=grade,
    )
    try:
        raw = await llm_service.chat(
            prompt=user_prompt,
            system_message=_SYSTEM_PROMPT_ZH,
            model="qwen",
            temperature=0.45,
            max_tokens=1600,
            user_id=user_id,
            organization_id=organization_id,
            request_type="showcase_ai_copy",
            diagram_type=None,
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            skip_load_balancing=True,
            response_format={"type": "json_object"},
            dashscope_model=SHOWCASE_AI_COPY_MODEL,
        )
    except LLM_PIPELINE_ERRORS:
        logger.exception("[ShowcaseAI] llm chat failed model=%s", SHOWCASE_AI_COPY_MODEL)
        raise

    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    text = str(raw).strip()
    if not text:
        raise ValueError("empty_llm_response")
    parsed = parse_json_object(text)
    return normalize_ai_copy_fields(parsed)


async def stream_teaching_design_copy(
    *,
    document_text: str,
    title: str,
    subject: str,
    grade: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    endpoint_path: str,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream qwen3.7-flash teaching-copy as SSE-ready event dicts.

    Yields ``fields`` snapshots while tokens arrive, then ``done`` with
    normalized fields, or ``error`` on failure.
    """
    user_prompt = _build_teaching_copy_user_prompt(
        document_text=document_text,
        title=title,
        subject=subject,
        grade=grade,
    )
    buffer = ""
    last_snapshot: Dict[str, str] = {}
    try:
        async for chunk in llm_service.chat_stream(
            prompt=user_prompt,
            system_message=_SYSTEM_PROMPT_ZH,
            model="qwen",
            temperature=0.45,
            max_tokens=1600,
            user_id=user_id,
            organization_id=organization_id,
            request_type="showcase_ai_copy",
            diagram_type=None,
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            skip_load_balancing=True,
            yield_structured=False,
            response_format={"type": "json_object"},
            dashscope_model=SHOWCASE_AI_COPY_MODEL,
        ):
            if chunk is None:
                continue
            if isinstance(chunk, dict):
                continue
            piece = str(chunk)
            if not piece:
                continue
            buffer += piece
            snapshot = extract_partial_ai_copy_fields(buffer)
            if snapshot and snapshot != last_snapshot:
                last_snapshot = dict(snapshot)
                yield {"event": "fields", **snapshot}
    except LLM_PIPELINE_ERRORS:
        logger.exception("[ShowcaseAI] llm stream failed model=%s", SHOWCASE_AI_COPY_MODEL)
        raise

    text = buffer.strip()
    if not text:
        raise ValueError("empty_llm_response")
    parsed = parse_json_object(text)
    fields = normalize_ai_copy_fields(parsed)
    yield {
        "event": "done",
        "description": fields["description"],
        "design_highlights": fields["design_highlights"],
        "teaching_reflection": fields["teaching_reflection"],
        "model": SHOWCASE_AI_COPY_MODEL,
    }
