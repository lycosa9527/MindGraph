"""Detect a photographed thinking map or mind map with qwen3.8-flash.

The prompt lists the diagram types. This module parses that JSON and keeps
only labels that are present. It does not call a generation agent.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from agents.core.agent_utils import extract_json_from_response
from config.dashscope_urls import build_dashscope_headers
from config.settings import config
from prompts.vision_diagram import VISION_DIAGRAM_PROMPT_EN, VISION_DIAGRAM_PROMPT_ZH
from services.knowledge.document_ocr import parse_dashscope_multimodal_text
from services.knowledge.vision_diagram_spec import (
    normalize_diagram_type,
    sanitize_diagram_spec,
    topic_from_diagram_spec,
)

# Same bar as the mind-map detector: below this, do not offer an import.
DIAGRAM_CONFIDENCE_THRESHOLD = 0.55

# The image import that was checked against the desktop samples.
VISION_DIAGRAM_MODEL = "qwen3.8-flash"


@dataclass(frozen=True)
class VisionDiagramResult:
    """Parsed type plus a loader-ready spec, when the photo is a diagram."""

    recognized: bool
    diagram_type: str
    confidence: float
    reason: str
    spec: Optional[Dict[str, Any]]
    topic: str
    raw_text: str


def _normalize_confidence(raw: Any) -> float:
    """Clamp confidence to [0, 1]."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _prompt_for(language: str) -> str:
    """Chinese prompt for zh UI; English otherwise. No generation language footer."""
    if (language or "zh").lower().startswith("zh"):
        return VISION_DIAGRAM_PROMPT_ZH
    return VISION_DIAGRAM_PROMPT_EN


def _empty_result(reason: str, raw_text: str = "") -> VisionDiagramResult:
    """A photo that is not a usable diagram."""
    return VisionDiagramResult(
        recognized=False,
        diagram_type="",
        confidence=0.0,
        reason=reason,
        spec=None,
        topic="",
        raw_text=raw_text,
    )


def parse_vision_diagram_payload(raw_text: str) -> VisionDiagramResult:
    """Parse model text into a diagram type and a sanitized spec."""
    text = (raw_text or "").strip()
    if not text:
        return _empty_result("empty_response")

    parsed = extract_json_from_response(text, allow_partial=True)
    if not isinstance(parsed, dict):
        return _empty_result("unparseable_json", text)

    confidence = _normalize_confidence(parsed.get("confidence"))
    reason = str(parsed.get("reason") or "").strip()[:300]
    diagram_type = normalize_diagram_type(parsed.get("diagram_type"))
    if not diagram_type:
        return VisionDiagramResult(
            recognized=False,
            diagram_type="",
            confidence=confidence,
            reason=reason or "not_a_diagram",
            spec=None,
            topic="",
            raw_text=text,
        )

    spec = sanitize_diagram_spec(diagram_type, parsed.get("spec"))
    if spec is None:
        return VisionDiagramResult(
            recognized=False,
            diagram_type=diagram_type,
            confidence=confidence,
            reason=reason or "spec_invalid",
            spec=None,
            topic="",
            raw_text=text,
        )
    if confidence < DIAGRAM_CONFIDENCE_THRESHOLD:
        return VisionDiagramResult(
            recognized=False,
            diagram_type=diagram_type,
            confidence=confidence,
            reason=reason or "below_confidence_threshold",
            spec=None,
            topic="",
            raw_text=text,
        )
    return VisionDiagramResult(
        recognized=True,
        diagram_type=diagram_type,
        confidence=confidence,
        reason=reason,
        spec=spec,
        topic=topic_from_diagram_spec(diagram_type, spec),
        raw_text=text,
    )


def dashscope_vision_diagram(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    language: str = "zh",
) -> VisionDiagramResult:
    """Call qwen3.8-flash to name the diagram and copy its labels."""
    api_key = config.QWEN_API_KEY
    if not api_key:
        raise ValueError("DashScope API key required for vision diagram import")

    resolved_mime = mime_type if mime_type.startswith("image/") else "image/jpeg"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    headers = build_dashscope_headers(
        api_key,
        workspace_id=config.DASHSCOPE_WORKSPACE_ID,
    )
    payload = {
        "model": VISION_DIAGRAM_MODEL,
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": [{"text": _prompt_for(language)}],
                },
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{resolved_mime};base64,{image_base64}"},
                        {"text": ("Name the diagram type and copy every visible label. Return JSON only.")},
                    ],
                },
            ]
        },
        "parameters": {
            "enable_thinking": False,
        },
    }
    base_url = config.DASHSCOPE_API_URL
    url = f"{base_url}services/aigc/multimodal-generation/generation"
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
    raw_text = parse_dashscope_multimodal_text(result)
    return parse_vision_diagram_payload(raw_text)


async def detect_and_rebuild_diagram_from_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    language: str = "zh",
) -> VisionDiagramResult:
    """Async wrapper around the blocking DashScope vision call."""
    return await asyncio.to_thread(
        dashscope_vision_diagram,
        image_bytes,
        mime_type,
        language,
    )


__all__ = [
    "VISION_DIAGRAM_MODEL",
    "VisionDiagramResult",
    "detect_and_rebuild_diagram_from_image",
    "parse_vision_diagram_payload",
]
