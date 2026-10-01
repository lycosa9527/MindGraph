"""Turn extracted document or page text into the open diagram's spec.

Mind maps keep the long-content agent. Every other registered type uses that
type's existing generator, with a short topic so ``{topic}`` prompts stay a
label.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Optional

from agents import get_agent, is_agent_available
from services.diagram.thinking_map_patterns import normalize_diagram_type

_FILENAME = re.compile(
    r"^[^\\/]+\.(pdf|docx?|pptx?|xlsx?|txt|md|csv|png|jpe?g|webp|mp3|wav|m4a)$",
    re.IGNORECASE,
)
_HEADING = re.compile(r"^#+\s*")
_GENERIC_TITLES = frozenset(
    {
        "document summary",
        "image",
        "upload",
        "document",
    }
)
_LONG_SOURCE_TYPES = frozenset({"double_bubble_map", "bridge_map"})
_TOPIC_LIMIT = 40
_EXCERPT_LIMIT = 600
_INSTRUCTION_LIMIT = 300


def resolve_content_diagram_slug(raw: Optional[str]) -> str:
    """Map a request slug to ``mindmap`` or a registered agent type."""
    slug = normalize_diagram_type(raw)
    if slug in ("", "mindmap", "mind_map"):
        return "mindmap"
    if not is_agent_available(slug):
        raise ValueError(slug)
    return slug


def content_agent_user_prompt(
    diagram_type: str,
    *,
    page_title: Optional[str],
    page_content: str,
    topic_hint: Optional[str] = None,
    generation_instructions: Optional[str] = None,
) -> str:
    """Prompt for a type agent. Short types stay a topic; comparison maps keep an excerpt."""
    topic = _pick_topic(topic_hint, page_title, page_content)
    if diagram_type not in _LONG_SOURCE_TYPES:
        return topic or "主题"
    excerpt = _compact(page_content, _EXCERPT_LIMIT)
    parts: list[str] = []
    if topic:
        parts.append(topic)
    if excerpt and excerpt != topic:
        parts.append(excerpt)
    prompt = "\n".join(parts) if parts else "主题"
    note = _compact(generation_instructions or "", _INSTRUCTION_LIMIT)
    if note:
        prompt = f"{prompt}\n{note}"
    return prompt


async def generate_non_mindmap_from_content(
    *,
    diagram_type: str,
    page_content: str,
    language: str,
    page_title: Optional[str],
    topic_hint: Optional[str],
    user_id: Optional[int],
    organization_id: Optional[int],
    endpoint_path: str,
    generation_instructions: Optional[str],
) -> dict[str, Any]:
    """Call the diagram type's existing agent."""
    agent = get_agent(diagram_type)
    if agent is None:
        raise ValueError(diagram_type)
    prompt = content_agent_user_prompt(
        diagram_type,
        page_title=page_title,
        page_content=page_content,
        topic_hint=topic_hint,
        generation_instructions=generation_instructions,
    )
    result = await agent.generate_graph(
        prompt,
        language=language,
        user_id=user_id,
        organization_id=organization_id,
        request_type="diagram_generation",
        endpoint_path=endpoint_path,
    )
    if isinstance(result, dict) and "diagram_type" not in result:
        result["diagram_type"] = diagram_type
    return result


def _pick_topic(topic_hint: Optional[str], page_title: Optional[str], page_content: str) -> str:
    for candidate in (topic_hint, page_title, _first_topic_line(page_content)):
        topic = _usable_title(candidate)
        if topic:
            return _clip_topic(topic)
    return ""


def _usable_title(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text or _FILENAME.match(text):
        return ""
    if text.casefold() in _GENERIC_TITLES:
        return ""
    return text


def _first_topic_line(content: str) -> str:
    for raw in content.splitlines():
        line = _HEADING.sub("", raw.strip()).strip("`*_ ")
        if not line or line.startswith("!["):
            continue
        return line
    return ""


def _clip_topic(text: str) -> str:
    compact = " ".join(text.split())
    for sep in ("。", "！", "？", ".", "!", "?"):
        index = compact.find(sep)
        if 0 < index <= _TOPIC_LIMIT:
            compact = compact[:index]
            break
    return compact[:_TOPIC_LIMIT].strip()


def _compact(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact[:limit].strip()
