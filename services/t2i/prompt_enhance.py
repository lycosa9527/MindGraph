"""K12 classroom prompt enhancement for ZhiHui image generation."""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.llm import llm_service
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_ENHANCE_SYSTEM = """You are an expert K12 teacher and educational content creator \
specializing in creating engaging visual materials for classroom instruction.

Your task is to transform a simple image generation prompt into a detailed, \
educationally-focused description for high-quality K12 classroom images.

IMPORTANT SAFETY GUIDELINES - STRICTLY FOLLOW THESE RULES:
- ONLY create prompts for educational, classroom-appropriate content
- AVOID any controversial, political, religious, or sensitive topics
- NO violence, weapons, or harmful content
- NO adult content, explicit material, or inappropriate themes
- NO copyrighted characters, brands, or trademarked content
- NO content that could offend cultural or religious groups
- FOCUS on academic subjects, nature, science, art, and positive learning themes
- CRITICAL: The final generated image should contain NO text, words, letters, numbers, or written characters of any kind
- NO signs, labels, banners, posters with text, or any written content should appear in the image
- NO Chinese characters, English text, or any language symbols should be rendered
- Focus on visual elements only: objects, scenes, colors, shapes, and visual concepts
- If the prompt mentions text elements, describe the visual appearance without including the actual text content

Enhance the prompt with educational context, age-appropriate content, visual learning elements, and classroom-friendly engagement. Keep the enhanced prompt under 250 words.

Return ONLY the enhanced prompt text, with no preamble."""


async def enhance_prompt_for_k12(
    original_prompt: str,
    *,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
) -> tuple[str, Optional[dict[str, Any]]]:
    """
    Enhance a user prompt for classroom image generation.

    Returns (enhanced_or_original_prompt, usage_data_or_none).
    """
    prompt = (original_prompt or "").strip()
    if not prompt:
        return prompt, None

    user_message = f'Original prompt: "{prompt}"\n\nEnhanced prompt:'
    try:
        response, usage_data = await llm_service.chat_with_usage(
            prompt=user_message,
            model="qwen",
            max_tokens=400,
            temperature=0.7,
            system_message=_ENHANCE_SYSTEM,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type="t2i_generation",
            endpoint_path="/api/generate-text-to-image",
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[T2I] Prompt enhancement failed: %s", exc)
        return prompt, None

    enhanced = (response or "").strip()
    if not enhanced:
        logger.warning("[T2I] Empty enhancement response; using original prompt")
        return prompt, usage_data
    logger.info(
        "[T2I] Prompt enhanced original_len=%s enhanced_len=%s",
        len(prompt),
        len(enhanced),
    )
    return enhanced, usage_data
