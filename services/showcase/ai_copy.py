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
from typing import Any, Dict, Optional

from services.knowledge.document_processor import get_document_processor
from services.llm import llm_service
from services.utils.error_types import JSON_PARSE_ERRORS, LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

SHOWCASE_AI_COPY_MODEL = "qwen3.7-flash"
SHOWCASE_AI_COPY_MAX_INPUT_CHARS = 32000
SHOWCASE_AI_COPY_MAX_FIELD_CHARS = 1200
# Per-field target (~200) × 3 fields ≈ 600 字 total.
SHOWCASE_AI_COPY_TARGET_CHARS_PER_FIELD = 200
SHOWCASE_AI_COPY_TARGET_CHARS_TOTAL = 600

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
- 字段：description（教学设计简介）、design_highlights（设计亮点）、\
teaching_reflection（教学反思）。
- 每个字段写成一整段连贯中文（完整句子），不要分条、不要项目符号、不要用换行罗列；\
在段落里自然写清「图示/工具 + 思维类型 + 作用」。
- 字数硬性目标：教学设计简介、设计亮点、教学反思各约 200 字（建议 190–210 字），\
三字段合计约 600 字；不要明显偏短，也不要某一字段独长。
- 紧扣学科、年级与文档内容；文档未写明的图示或活动不要虚构。"""

_USER_PROMPT_TEMPLATE_ZH = """\
【案例元信息】
标题：{title}
学科：{subject}
年级：{grade}

【教学设计文档正文】
{document_text}

请输出 JSON：三个字段各约 200 字、合计约 600 字；每字段一整段完整句子；\
写清图示与思维，但用语要通俗、给中小学老师减负；勿分条、勿论文腔。\
{{"description":"...","design_highlights":"...","teaching_reflection":"..."}}"""


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
    """Normalize LLM JSON into the three showcase teaching-design fields."""
    description = _clean_field(parsed.get("description") or parsed.get("教学设计简介") or parsed.get("intro"))
    highlights = _clean_field(
        parsed.get("design_highlights")
        or parsed.get("designHighlights")
        or parsed.get("设计亮点")
        or parsed.get("highlights")
    )
    reflection = _clean_field(
        parsed.get("teaching_reflection")
        or parsed.get("teachingReflection")
        or parsed.get("教学反思")
        or parsed.get("reflection")
    )
    if not description and not highlights and not reflection:
        raise ValueError("empty_ai_copy_fields")
    return {
        "description": description,
        "design_highlights": highlights,
        "teaching_reflection": reflection,
    }


def extract_document_text(file_path: str) -> str:
    """Extract plain text from a teaching-design upload (.pdf/.doc/.docx)."""
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
    """Call qwen3.7-flash and return normalized showcase copy fields."""
    user_prompt = _USER_PROMPT_TEMPLATE_ZH.format(
        title=title.strip() or "未命名案例",
        subject=subject.strip() or "未指定",
        grade=grade.strip() or "未指定",
        document_text=document_text.strip(),
    )
    try:
        raw = await llm_service.chat(
            prompt=user_prompt,
            system_message=_SYSTEM_PROMPT_ZH,
            model="qwen",
            temperature=0.45,
            max_tokens=2400,
            user_id=user_id,
            organization_id=organization_id,
            request_type="showcase_ai_copy",
            diagram_type=None,
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            skip_load_balancing=False,
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
