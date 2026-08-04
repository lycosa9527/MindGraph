"""
Showcase diagram-case / template AI copy: extract node text then draft case fields.

Uses DashScope ``qwen3.7-flash`` with an education-focused prompt (思维发展型课堂).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterable
from typing import Any, Dict, List, Optional

from services.kitty.infra.bootstrap.kitty_native_spec import native_spec_to_pseudo_nodes
from services.llm import llm_service
from services.showcase.ai_copy import (
    SHOWCASE_AI_COPY_MAX_INPUT_CHARS,
    SHOWCASE_AI_COPY_MODEL,
    clean_ai_copy_field,
    extract_partial_json_string_fields,
    parse_json_object,
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

_SYSTEM_PROMPT_ZH = """\
你是面向中小学教师的思维发展型课堂教研助手（MindGraph 案例广场）。用户会提供一份图示\
（思维可视化图）的节点文字内容，请据此撰写可直接发布的中文文案。平台强调「思维可视化\
+ 思维策略」，文案必须写出具体图示类型与课堂用法，不能只写空泛目标。

读者是忙碌的中小学老师：用语要口语化、好读、好懂，减轻阅读负担。
- 多用短句和日常教研说法，少用论文腔、翻译腔和堆叠术语。
- 尽量少用或改写：脚手架、元认知、概念变式、过程性变式、认知负荷、显性化、\
建构、进阶、嵌入、嵌套、任务群、素养落地等偏学术说法；改成老师一听就懂的话\
（如：搭梯子、回头看自己的想法、换一种问法、负担太大、说清楚、自己想明白）。
- 图示名称（气泡图、双气泡图、流程图、思维导图等）和常见思维说法（比较、因果、\
批判性思考）可保留，但要用「谁在什么环节用它做什么」说清楚，不要只甩术语。
- 直接写内容，勿提及 AI、模型、节点提取、Markdown 或本提示本身。

每个字段必须尽量落到图示中的真实内容，并点明：
1) 这是什么图示/思维工具，图里主要画了哪些关键信息（图示没写的不要编）；
2) 主要练什么思维（如：观察归类、比较异同、找因果关系、按顺序梳理、打比方迁移、\
质疑证据、多角度看问题等）；
3) 在课堂上可以怎么用、帮助学生解决什么困难。

输出要求：
- 仅输出一个 JSON 对象（不要代码围栏、不要额外说明）。
- 字段仅两项：description（图示简介）、classroom_application（课堂应用）。\
不要输出其他字段。
- 每个字段写成一整段连贯中文（完整句子），不要分条、不要项目符号、不要用换行罗列；\
在段落里自然写清「图示/工具 + 思维类型 + 作用」。
- 字数硬性目标：图示简介、课堂应用各约 200 字（建议 190–210 字），\
两字段合计约 400 字；不要明显偏短，也不要某一字段独长。
- 紧扣学科、年级与图示内容；图示未写明的活动不要虚构。"""

_USER_PROMPT_TEMPLATE_ZH = """\
【案例元信息】
标题：{title}
学科：{subject}
年级：{grade}
图示类型：{diagram_type}

【图示节点文字】
{diagram_text}

请输出 JSON：仅 description 与 classroom_application，各约 200 字、合计约 400 字；\
每字段一整段完整句子；写清图示与思维，但用语要通俗、给中小学老师减负；\
勿分条、勿论文腔。\
{{"description":"...","classroom_application":"..."}}"""


def _collect_node_texts(nodes: Iterable[Any]) -> List[str]:
    texts: List[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        text = node.get("text")
        if text is None:
            continue
        cleaned = str(text).strip()
        if cleaned:
            texts.append(cleaned)
    return texts


def _walk_nested_text(value: Any, sink: List[str], *, depth: int = 0) -> None:
    """Collect string ``text`` / ``label`` fields from nested dict/list structures."""
    if depth > 40:
        return
    if isinstance(value, dict):
        for key in ("text", "label", "topic", "title", "name"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                sink.append(raw.strip())
        for child_key in ("children", "branches", "nodes", "items", "parts", "subparts"):
            child = value.get(child_key)
            if isinstance(child, list):
                for item in child:
                    _walk_nested_text(item, sink, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _walk_nested_text(item, sink, depth=depth + 1)


def extract_diagram_text(
    spec: Dict[str, Any],
    diagram_type: str,
) -> str:
    """Extract plain node labels from a diagram spec for LLM prompting."""
    texts: List[str] = []
    nodes = spec.get("nodes")
    if isinstance(nodes, list) and nodes:
        texts.extend(_collect_node_texts(nodes))
    else:
        pseudo = native_spec_to_pseudo_nodes(spec, diagram_type)
        if pseudo:
            texts.extend(_collect_node_texts(pseudo))
        else:
            _walk_nested_text(spec, texts)

    # Stable unique order (first occurrence wins).
    seen: set[str] = set()
    unique: List[str] = []
    for item in texts:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)

    cleaned = "\n".join(unique).strip()
    if not cleaned:
        raise ValueError("no_text_extracted")
    if len(cleaned) > SHOWCASE_AI_COPY_MAX_INPUT_CHARS:
        cleaned = cleaned[:SHOWCASE_AI_COPY_MAX_INPUT_CHARS]
    return cleaned


def extract_diagram_texts(
    specs: List[Dict[str, Any]],
    diagram_type: str,
) -> str:
    """Join text from one or more diagram specs (gallery cases)."""
    chunks: List[str] = []
    for index, spec in enumerate(specs, start=1):
        try:
            chunk = extract_diagram_text(spec, diagram_type)
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
    return _USER_PROMPT_TEMPLATE_ZH.format(
        title=title.strip() or "未命名案例",
        subject=subject.strip() or "未指定",
        grade=grade.strip() or "未指定",
        diagram_type=diagram_type.strip() or "未指定",
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
