"""
Diagram type detection.

This module provides LLM-based diagram type detection using semantic understanding.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging

from prompts import get_prompt

from agents.core.utils import validate_inputs
from services.llm import llm_service

logger = logging.getLogger(__name__)


async def _detect_diagram_type_from_prompt(
    user_prompt: str,
    language: str,
    model: str = 'qwen',
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None
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
        # Validate inputs
        validate_inputs(user_prompt, language)

        # Check if prompt is too vague or complex (basic heuristics before LLM)
        prompt_words = user_prompt.strip().split()
        is_too_short = len(prompt_words) < 2
        is_too_long = len(prompt_words) > 100

        # Get classification prompt from centralized system
        classification_prompt = get_prompt("classification", language, "generation")
        classification_prompt = classification_prompt.format(user_prompt=user_prompt)

        # Use middleware directly - clean and efficient!
        response = await llm_service.chat(
            prompt=classification_prompt,
            model=model,
            max_tokens=50,
            temperature=0.3,
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path
        )

        # Extract diagram type from response
        detected_type = response.strip().lower()

        # Validate the detected type - only include working diagram types
        # 8 thinking maps + 1 mindmap (concept_map is work in progress)
        valid_types = {
            'circle_map', 'bubble_map', 'double_bubble_map',
            'brace_map', 'bridge_map', 'tree_map',
            'flow_map', 'multi_flow_map',
            'mind_map'
        }

        # Determine clarity based on LLM response and heuristics
        clarity = 'clear'
        has_topic = True

        # Check if LLM explicitly returned "unclear"
        if detected_type == 'unclear':
            clarity = 'very_unclear'
            has_topic = False
            detected_type = 'mind_map'  # Default fallback
            logger.warning(
                "LLM explicitly returned 'unclear' for prompt: '%s'", user_prompt
            )
        elif detected_type not in valid_types:
            # LLM returned something invalid
            clarity = 'very_unclear'
            has_topic = False
            detected_type = 'mind_map'  # Default fallback
            logger.warning(
                "LLM returned invalid type '%s', prompt may be too complex: '%s'",
                detected_type, user_prompt
            )
        elif is_too_short or is_too_long:
            # Prompt length is suspicious
            clarity = 'unclear'
            logger.debug("Prompt length is suspicious (words: %d)", len(prompt_words))

        result = {
            'diagram_type': detected_type,
            'clarity': clarity,
            'has_topic': has_topic
        }

        logger.debug(
            "LLM classification: '%s' -> %s (clarity: %s)",
            user_prompt, detected_type, clarity
        )
        return result

    except ValueError as e:
        logger.error("Input validation failed: %s", e)
        return {'diagram_type': 'mind_map', 'clarity': 'very_unclear', 'has_topic': False}
    except Exception as e:  # pylint: disable=broad-except
        logger.error("LLM classification failed: %s", e)
        return {'diagram_type': 'mind_map', 'clarity': 'very_unclear', 'has_topic': False}
