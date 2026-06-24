"""
Diagram type detection.

This module provides LLM-based diagram type detection using semantic understanding.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import re

from agents.core.llm_spec_stream import dispatch_llm_chat
from agents.core.utils import validate_inputs
from prompts import get_prompt
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

VALID_DIAGRAM_TYPES = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "brace_map",
        "bridge_map",
        "tree_map",
        "flow_map",
        "multi_flow_map",
        "mind_map",
    }
)

_TYPE_ALIASES = {
    "mindmap": "mind_map",
    "mind-map": "mind_map",
    "tree-map": "tree_map",
    "flow-map": "flow_map",
}


def _normalize_type_token(token: str) -> str | None:
    cleaned = token.strip().lower().strip("\"`'.,;:")
    if not cleaned or cleaned == "unclear":
        return cleaned or None
    if cleaned in VALID_DIAGRAM_TYPES:
        return cleaned
    return _TYPE_ALIASES.get(cleaned)


def _extract_diagram_type_from_llm_response(raw: str) -> str | None:
    """Parse the first valid diagram type token from an LLM classification response."""
    cleaned = raw.strip().lower()
    if not cleaned:
        return None

    direct = _normalize_type_token(cleaned)
    if direct in VALID_DIAGRAM_TYPES or direct == "unclear":
        return direct

    for token in re.split(r"[\s,;]+", cleaned):
        normalized = _normalize_type_token(token)
        if normalized in VALID_DIAGRAM_TYPES:
            return normalized

    for dtype in sorted(VALID_DIAGRAM_TYPES, key=len, reverse=True):
        if dtype in cleaned:
            return dtype

    if "unclear" in cleaned:
        return "unclear"

    return None


def _default_detection_result(
    diagram_type: str = "mind_map",
    clarity: str = "unclear",
    has_topic: bool = True,
) -> dict:
    return {
        "diagram_type": diagram_type,
        "clarity": clarity,
        "has_topic": has_topic,
    }


async def _detect_diagram_type_from_prompt(
    user_prompt: str,
    language: str,
    model: str = "qwen",
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type="diagram_generation",
    endpoint_path=None,
    phase_emit=None,
) -> dict:
    """
    LLM-based diagram type detection using semantic understanding.

    Args:
        user_prompt: User's input prompt
        language: Language ('zh' or 'en')
        model: LLM model to use ('qwen', 'deepseek', 'kimi', 'doubao')

    Returns:
        dict: {'diagram_type': str, 'clarity': str, 'has_topic': bool}
              clarity can be 'clear', 'unclear', or 'very_unclear'
    """
    try:
        validate_inputs(user_prompt, language)

        prompt_words = user_prompt.strip().split()
        is_too_short = len(prompt_words) < 2
        is_too_long = len(prompt_words) > 100

        classification_prompt = get_prompt("classification", language, "generation")
        classification_prompt = classification_prompt.format(user_prompt=user_prompt)

        response = await dispatch_llm_chat(
            phase_emit=phase_emit,
            prompt=classification_prompt,
            model=model,
            max_tokens=50,
            temperature=0.3,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path,
        )
        response_text = str(response) if not isinstance(response, dict) else str(response.get("content", response))

        detected_type = _extract_diagram_type_from_llm_response(response_text)
        clarity = "clear"
        has_topic = True

        if detected_type == "unclear" or detected_type is None:
            clarity = "unclear"
            detected_type = "mind_map"
            logger.info(
                "Classification ambiguous for prompt %r — defaulting to mind_map",
                user_prompt[:80],
            )
        elif is_too_short or is_too_long:
            clarity = "unclear"
            logger.debug("Prompt length is suspicious (words: %d)", len(prompt_words))

        result = {
            "diagram_type": detected_type,
            "clarity": clarity,
            "has_topic": has_topic,
        }

        logger.debug(
            "LLM classification: %r -> %s (clarity: %s)",
            user_prompt[:80],
            detected_type,
            clarity,
        )
        return result

    except ValueError as exc:
        logger.error("Input validation failed: %s", exc)
        return _default_detection_result(clarity="very_unclear", has_topic=False)
    except LLM_PIPELINE_ERRORS as exc:
        logger.error("LLM classification failed: %s", exc)
        return _default_detection_result()
