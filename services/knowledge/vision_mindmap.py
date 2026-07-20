"""Vision mind-map detect + structure rebuild via DashScope multimodal.

Uses ``DASHSCOPE_VISION_MODEL`` (default ``qwen3.6-flash``) to decide whether an
image is a hand-drawn / photographed mind map (circles, bubbles, radial layout)
and, when it is, reconstruct a ``topic`` + nested ``children`` JSON spec.

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
from config.settings import config
from prompts import get_prompt
from services.knowledge.document_ocr import parse_dashscope_multimodal_text
from services.utils.error_types import HTTP_CLIENT_ERRORS, JSON_PARSE_ERRORS

# Auto-detect threshold: below this, treat as a normal document photo.
MINDMAP_CONFIDENCE_THRESHOLD = 0.55

VISION_MINDMAP_CALL_ERRORS: tuple[type[BaseException], ...] = (
    *HTTP_CLIENT_ERRORS,
    *JSON_PARSE_ERRORS,
    httpx.HTTPError,
    KeyError,
)


@dataclass(frozen=True)
class VisionMindmapResult:
    """Parsed vision detect + optional structure rebuild."""

    is_mindmap: bool
    confidence: float
    reason: str
    spec: Optional[Dict[str, Any]]
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


def _node_text(node: Dict[str, Any]) -> str:
    """Prefer canonical ``text``, fall back to ``label``."""
    text = node.get("text") or node.get("label") or ""
    return str(text).strip()


def _sanitize_children(nodes: Any, *, depth: int = 0) -> list[Dict[str, Any]]:
    """Keep only dict nodes with non-empty text; cap nesting depth."""
    if not isinstance(nodes, list) or depth > 6:
        return []
    cleaned: list[Dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        label = _node_text(node)
        if not label:
            continue
        node_id = str(node.get("id") or f"n_{depth}_{index}").strip() or f"n_{depth}_{index}"
        entry: Dict[str, Any] = {"id": node_id[:64], "text": label[:200]}
        nested = _sanitize_children(node.get("children"), depth=depth + 1)
        if nested:
            entry["children"] = nested
        cleaned.append(entry)
    return cleaned


def sanitize_mindmap_spec(raw_spec: Any) -> Optional[Dict[str, Any]]:
    """Normalize vision JSON into a mind-map spec or return None."""
    if not isinstance(raw_spec, dict):
        return None
    topic = str(raw_spec.get("topic") or "").strip()
    if not topic:
        return None
    children = _sanitize_children(raw_spec.get("children"))
    if not children:
        return None
    return {"topic": topic[:200], "children": children}


def parse_vision_mindmap_payload(raw_text: str) -> VisionMindmapResult:
    """Parse model text into detect + optional spec."""
    text = (raw_text or "").strip()
    if not text:
        return VisionMindmapResult(
            is_mindmap=False,
            confidence=0.0,
            reason="empty_response",
            spec=None,
            raw_text="",
        )

    parsed = extract_json_from_response(text, allow_partial=True)
    if not isinstance(parsed, dict):
        return VisionMindmapResult(
            is_mindmap=False,
            confidence=0.0,
            reason="unparseable_json",
            spec=None,
            raw_text=text,
        )

    confidence = _normalize_confidence(parsed.get("confidence"))
    reason = str(parsed.get("reason") or "").strip()[:300]
    flagged = bool(parsed.get("is_mindmap"))
    spec = sanitize_mindmap_spec(parsed.get("spec")) if flagged else None
    is_mindmap = flagged and spec is not None and confidence >= MINDMAP_CONFIDENCE_THRESHOLD
    if flagged and spec is None:
        reason = reason or "mindmap_flagged_but_spec_invalid"
        is_mindmap = False
    elif flagged and confidence < MINDMAP_CONFIDENCE_THRESHOLD:
        reason = reason or "below_confidence_threshold"
        is_mindmap = False
        spec = None

    return VisionMindmapResult(
        is_mindmap=is_mindmap,
        confidence=confidence,
        reason=reason,
        spec=spec,
        raw_text=text,
    )


def dashscope_vision_mindmap(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    language: str = "zh",
) -> VisionMindmapResult:
    """Call DashScope multimodal to detect + rebuild a mind map from an image."""
    api_key = config.QWEN_API_KEY
    if not api_key:
        raise ValueError("DashScope API key required for vision mind map")

    system_prompt = get_prompt("mind_map", language, "vision_handdrawn")
    if not system_prompt:
        raise ValueError("Missing mind_map vision_handdrawn prompt")

    resolved_mime = mime_type if mime_type.startswith("image/") else "image/jpeg"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # qwen3.5 / qwen3.6 vision defaults to thinking ON, which burns large
    # reasoning_tokens (often 10–20s+). Structured JSON rebuild does not need it.
    payload = {
        "model": config.DASHSCOPE_VISION_MODEL,
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": [{"text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{resolved_mime};base64,{image_base64}"},
                        {
                            "text": (
                                "Detect whether this image is a mind map / concept map "
                                "with a visible radial or hierarchical layout. "
                                "If yes, rebuild the exact node hierarchy as JSON."
                            )
                        },
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
    return parse_vision_mindmap_payload(raw_text)


async def detect_and_rebuild_mindmap_from_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    language: str = "zh",
) -> VisionMindmapResult:
    """Async wrapper around the blocking DashScope vision call."""
    return await asyncio.to_thread(
        dashscope_vision_mindmap,
        image_bytes,
        mime_type,
        language,
    )
