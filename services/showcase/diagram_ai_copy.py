"""
Showcase diagram-case / template AI copy: outline structure then draft case fields.

Uses DashScope ``qwen3.7-flash`` with an education-focused prompt (思维发展型课堂).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

from services.knowledge.document_ocr import (
    OCR_CALL_ERRORS,
    dashscope_vision_ocr,
    ocr_image_bytes,
)
from services.llm import llm_service
from services.showcase.ai_copy import (
    SHOWCASE_AI_COPY_MAX_INPUT_CHARS,
    SHOWCASE_AI_COPY_MODEL,
    clean_ai_copy_field,
    extract_partial_json_string_fields,
    parse_json_object,
)
from services.showcase.diagram_structure_outline import (
    build_diagram_structure_outline,
    diagram_type_zh_label,
    resolve_diagram_type,
)
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

_DIAGRAM_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "description": ("description", "图示简介", "intro"),
    "classroom_application": (
        "classroom_application",
        "classroomApplication",
        "课堂应用",
        "classroom_app",
    ),
}

_DIAGRAM_IMAGE_OCR_PROMPT = (
    "请提取图片中思维图示/图表的全部文字，尽量按从上到下、从中心到分支的顺序整理。"
    "保留标题、节点与标签原文。若几乎没有文字，用一两句中文概括图中可见主题与结构。"
)

_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_SYSTEM_PROMPT_ZH = """\
你是面向中小学教师的思维发展型课堂教研助手（MindGraph 案例广场）。用户会提供一份图示\
（思维可视化图）的「图示内容」——可能是系统从图示 JSON 解析出的结构概要（类型、层级与\
节点角色），也可能是从图示图片经 OCR / 视觉识别得到的文字，请据此撰写可直接发布的中文\
文案。平台强调「思维可视化 + 思维策略」，文案必须写出具体图示类型与课堂用法，不能只写\
空泛目标。

读者是忙碌的中小学老师：用语要口语化、好读、好懂，减轻阅读负担。
- 多用短句和日常教研说法，少用论文腔、翻译腔和堆叠术语。
- 尽量少用或改写：脚手架、元认知、概念变式、过程性变式、认知负荷、显性化、\
建构、进阶、嵌入、嵌套、任务群、素养落地等偏学术说法；改成老师一听就懂的话\
（如：搭梯子、回头看自己的想法、换一种问法、负担太大、说清楚、自己想明白）。
- 图示名称（气泡图、双气泡图、流程图、思维导图等）和常见思维说法（比较、因果、\
批判性思考）可保留，但要用「谁在什么环节用它做什么」说清楚，不要只甩术语。
- 直接写内容，勿提及 AI、模型、JSON、节点提取、Markdown 或本提示本身。

写作要点（必须做到）：
1) 先准确点明图示类型（以结构概要里的「图示类型」为准，如：这是一张思维导图），\
再概括结构长什么样（中心主题、一级分支、层级关系，或原因/结果、异同点等——\
按该图类型真实结构写）；
2) 简介里要落到图中真实主题与主要分支/要点，图示没写的不要编；
3) 点明主要练什么思维（如：观察归类、比较异同、找因果关系、按顺序梳理、打比方迁移、\
质疑证据、多角度看问题等）；
4) 课堂应用要能对应这张图的结构，说明怎么用、帮助学生解决什么困难。

输出要求：
- 仅输出一个 JSON 对象（不要代码围栏、不要额外说明）。
- 字段仅两项：description（图示简介）、classroom_application（课堂应用）。\
不要输出其他字段。
- 每个字段写成一整段连贯中文（完整句子），不要分条、不要项目符号、不要用换行罗列；\
在段落里自然写清「图示/工具 + 结构要点 + 思维类型 + 作用」。
- 字数硬性目标：图示简介、课堂应用各约 200 字（建议 190–210 字），\
两字段合计约 400 字；不要明显偏短，也不要某一字段独长。
- 紧扣学科、年级与图示结构；图示未写明的活动不要虚构。"""

_USER_PROMPT_TEMPLATE_ZH = """\
【案例元信息】
标题：{title}
学科：{subject}
年级：{grade}
图示类型：{diagram_type_zh}（{diagram_type}）

【图示内容】（结构概要或图片 OCR / 视觉识别文本；请据此分析后写文案）
{diagram_text}

请输出 JSON：仅 description 与 classroom_application，各约 200 字、合计约 400 字；\
description 开头先点明图示类型并概括结构，再落到真实内容；用语通俗、给中小学老师减负；\
勿分条、勿论文腔、勿编造图示内容里没有的内容。\
{{"description":"...","classroom_application":"..."}}"""


def extract_diagram_text(
    spec: Dict[str, Any],
    diagram_type: str,
) -> str:
    """Build a structural outline from a diagram spec for LLM prompting."""
    cleaned = build_diagram_structure_outline(spec, diagram_type).strip()
    if not cleaned:
        raise ValueError("no_text_extracted")
    if len(cleaned) > SHOWCASE_AI_COPY_MAX_INPUT_CHARS:
        cleaned = cleaned[:SHOWCASE_AI_COPY_MAX_INPUT_CHARS]
    return cleaned


def extract_diagram_texts(
    specs: List[Dict[str, Any]],
    diagram_type: str,
) -> str:
    """Join structural outlines from one or more diagram specs (gallery cases)."""
    chunks: List[str] = []
    for index, spec in enumerate(specs, start=1):
        try:
            per_type = resolve_diagram_type(spec, diagram_type)
            chunk = extract_diagram_text(spec, per_type)
        except ValueError:
            continue
        if len(specs) > 1:
            chunks.append(f"【图示 {index}】\n{chunk}")
        else:
            chunks.append(chunk)
    joined = "\n\n".join(chunks).strip()
    if not joined:
        raise ValueError("no_text_extracted")
    if len(joined) > SHOWCASE_AI_COPY_MAX_INPUT_CHARS:
        joined = joined[:SHOWCASE_AI_COPY_MAX_INPUT_CHARS]
    return joined


def _mime_for_image_suffix(suffix: str) -> str:
    return _IMAGE_MIME_BY_SUFFIX.get(suffix.lower(), "image/png")


def _ocr_one_diagram_image(image_bytes: bytes, mime_type: str) -> str:
    """OCR one gallery image via Qwen vision, with Tesseract soft fallback."""
    resolved_mime = mime_type if mime_type.startswith("image/") else "image/png"
    try:
        text = dashscope_vision_ocr(
            image_bytes,
            resolved_mime,
            prompt=_DIAGRAM_IMAGE_OCR_PROMPT,
        ).strip()
        if text:
            return text
    except (*OCR_CALL_ERRORS, ValueError) as exc:
        logger.warning("[ShowcaseDiagramAI] vision OCR failed: %s", exc)
    # Soft PNG/JPEG fallback path (Tesseract); never raises.
    return ocr_image_bytes(image_bytes).strip()


def extract_diagram_text_from_images(
    images: List[tuple[bytes, str]],
) -> str:
    """OCR gallery images into prompt text for diagram AI copy.

    Each item is ``(image_bytes, mime_type_or_filename_suffix)``.
    """
    chunks: List[str] = []
    for index, (image_bytes, mime_or_suffix) in enumerate(images, start=1):
        if not image_bytes:
            continue
        mime_type = mime_or_suffix
        if mime_or_suffix.startswith("."):
            mime_type = _mime_for_image_suffix(mime_or_suffix)
        elif "/" not in mime_or_suffix:
            mime_type = _mime_for_image_suffix(f".{mime_or_suffix.lstrip('.')}")
        text = _ocr_one_diagram_image(image_bytes, mime_type)
        if not text:
            continue
        if len(images) > 1:
            chunks.append(f"【图片 {index} OCR】\n{text}")
        else:
            chunks.append(f"【图片 OCR】\n{text}")
    joined = "\n\n".join(chunks).strip()
    if not joined:
        raise ValueError("no_text_extracted")
    if len(joined) > SHOWCASE_AI_COPY_MAX_INPUT_CHARS:
        joined = joined[:SHOWCASE_AI_COPY_MAX_INPUT_CHARS]
    return joined


def normalize_diagram_ai_copy_fields(parsed: Dict[str, Any]) -> Dict[str, str]:
    """Normalize LLM JSON into diagram showcase AI fields."""
    description = clean_ai_copy_field(parsed.get("description") or parsed.get("图示简介") or parsed.get("intro"))
    classroom = clean_ai_copy_field(
        parsed.get("classroom_application")
        or parsed.get("classroomApplication")
        or parsed.get("课堂应用")
        or parsed.get("classroom_app")
    )
    if not description and not classroom:
        raise ValueError("empty_ai_copy_fields")
    return {
        "description": description,
        "classroom_application": classroom,
    }


def extract_partial_diagram_ai_copy_fields(buffer: str) -> Dict[str, str]:
    """Extract diagram-copy string fields from an incomplete JSON stream buffer."""
    return extract_partial_json_string_fields(buffer, _DIAGRAM_FIELD_ALIASES)


def _build_diagram_copy_user_prompt(
    *,
    diagram_text: str,
    title: str,
    subject: str,
    grade: str,
    diagram_type: str,
) -> str:
    slug = (diagram_type or "").strip() or "未指定"
    return _USER_PROMPT_TEMPLATE_ZH.format(
        title=title.strip() or "未命名案例",
        subject=subject.strip() or "未指定",
        grade=grade.strip() or "未指定",
        diagram_type=slug,
        diagram_type_zh=diagram_type_zh_label(slug),
        diagram_text=diagram_text.strip(),
    )


async def generate_diagram_case_copy(
    *,
    diagram_text: str,
    title: str,
    subject: str,
    grade: str,
    diagram_type: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    endpoint_path: str,
) -> Dict[str, str]:
    """Call qwen3.7-flash and return diagram intro + classroom application."""
    user_prompt = _build_diagram_copy_user_prompt(
        diagram_text=diagram_text,
        title=title,
        subject=subject,
        grade=grade,
        diagram_type=diagram_type,
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
            request_type="showcase_ai_diagram_copy",
            diagram_type=diagram_type or None,
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            skip_load_balancing=True,
            response_format={"type": "json_object"},
            dashscope_model=SHOWCASE_AI_COPY_MODEL,
        )
    except LLM_PIPELINE_ERRORS:
        logger.exception("[ShowcaseAI] diagram llm chat failed model=%s", SHOWCASE_AI_COPY_MODEL)
        raise

    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    text = str(raw).strip()
    if not text:
        raise ValueError("empty_llm_response")
    parsed = parse_json_object(text)
    return normalize_diagram_ai_copy_fields(parsed)


async def stream_diagram_case_copy(
    *,
    diagram_text: str,
    title: str,
    subject: str,
    grade: str,
    diagram_type: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    endpoint_path: str,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream diagram-copy as SSE-ready event dicts (fields → done)."""
    user_prompt = _build_diagram_copy_user_prompt(
        diagram_text=diagram_text,
        title=title,
        subject=subject,
        grade=grade,
        diagram_type=diagram_type,
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
            request_type="showcase_ai_diagram_copy",
            diagram_type=diagram_type or None,
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
            snapshot = extract_partial_diagram_ai_copy_fields(buffer)
            if snapshot and snapshot != last_snapshot:
                last_snapshot = dict(snapshot)
                yield {"event": "fields", **snapshot}
    except LLM_PIPELINE_ERRORS:
        logger.exception(
            "[ShowcaseAI] diagram llm stream failed model=%s",
            SHOWCASE_AI_COPY_MODEL,
        )
        raise

    text = buffer.strip()
    if not text:
        raise ValueError("empty_llm_response")
    parsed = parse_json_object(text)
    fields = normalize_diagram_ai_copy_fields(parsed)
    yield {
        "event": "done",
        "description": fields["description"],
        "classroom_application": fields["classroom_application"],
        "model": SHOWCASE_AI_COPY_MODEL,
    }
