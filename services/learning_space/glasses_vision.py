"""Read a photographed learning sheet into a name and a mind-map spec.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from agents.core.agent_utils import extract_json_from_response
from config.dashscope_urls import build_dashscope_headers
from config.settings import config
from services.knowledge.document_ocr import parse_dashscope_multimodal_text
from services.knowledge.vision_mindmap import sanitize_mindmap_spec
from services.showcase.diagram_structure_outline import build_diagram_structure_outline
from services.utils.error_types import HTTP_CLIENT_ERRORS, JSON_PARSE_ERRORS

SHEET_OCR_MODEL = "qwen3.8-flash"
_OUTLINE_LIMIT = 4000

_PROMPT = (
    "This photo is a printed learning sheet. Read the handwriting and the printed text. "
    "Return JSON only, with keys student_name, class_name, and spec. "
    "student_name is the name written on the sheet, or an empty string. "
    "class_name is the class written on the sheet, or an empty string. "
    "spec is a mind map: {topic, children:[{text, children}]}. "
    "Include every visible node, including answers written into blank nodes."
)

VISION_SHEET_ERRORS: tuple[type[BaseException], ...] = (
    *HTTP_CLIENT_ERRORS,
    *JSON_PARSE_ERRORS,
    httpx.HTTPError,
    ValueError,
    KeyError,
)


@dataclass(frozen=True)
class LearningSheetRead:
    """Name, class, and diagram recovered from one photo."""

    student_name: str
    class_name: str
    spec: Optional[dict[str, Any]]
    error: str


def _clip(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def printed_diagram_outline(spec: Any) -> str:
    """Text of the diagram already stored for this sheet, for the OCR to match."""
    if not isinstance(spec, dict):
        return ""
    diagram_type = spec.get("type") if isinstance(spec.get("type"), str) else "mindmap"
    try:
        text = build_diagram_structure_outline(spec, str(diagram_type))
    except ValueError:
        return ""
    return text.strip()[:_OUTLINE_LIMIT]


def _prompt_for(reference: str) -> str:
    printed = reference.strip()
    if not printed:
        return _PROMPT
    return (
        f"{_PROMPT} The printed diagram on this sheet is:\n{printed}\n"
        "Keep that structure. Put handwritten words into the matching nodes."
    )


def parse_learning_sheet_read(raw_text: str) -> LearningSheetRead:
    """Parse the model JSON. A missing diagram is an error, a missing name is not."""
    parsed = extract_json_from_response((raw_text or "").strip(), allow_partial=True)
    if not isinstance(parsed, dict):
        return LearningSheetRead("", "", None, "unparseable_json")
    spec = sanitize_mindmap_spec(parsed.get("spec"))
    error = "" if spec is not None else "spec_missing"
    return LearningSheetRead(
        student_name=_clip(parsed.get("student_name"), 80),
        class_name=_clip(parsed.get("class_name"), 80),
        spec=spec,
        error=error,
    )


def dashscope_read_learning_sheet(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    reference: str = "",
) -> LearningSheetRead:
    """Call DashScope and parse one sheet photo. Blocking."""
    api_key = config.QWEN_API_KEY
    if not api_key:
        raise ValueError("DashScope API key required for learning sheet vision")
    resolved_mime = mime_type if mime_type.startswith("image/") else "image/jpeg"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    headers = build_dashscope_headers(api_key, workspace_id=config.DASHSCOPE_WORKSPACE_ID)
    payload = {
        "model": SHEET_OCR_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{resolved_mime};base64,{image_base64}"},
                        {"text": _prompt_for(reference)},
                    ],
                }
            ]
        },
        "parameters": {"enable_thinking": False},
    }
    base_url = config.DASHSCOPE_API_URL
    url = f"{base_url}services/aigc/multimodal-generation/generation"
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
    return parse_learning_sheet_read(parse_dashscope_multimodal_text(result))
