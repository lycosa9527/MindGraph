"""
Learning sheet detection and cleaning.

This module provides functions for detecting learning sheet requests and
cleaning prompts to generate actual content instead of meta-content.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import re

logger = logging.getLogger(__name__)


def _detect_learning_sheet_from_prompt(user_prompt: str, language: str = 'zh') -> bool:
    """
    Detect if the prompt is requesting a learning sheet.

    Args:
        user_prompt: User's input prompt
        language: Language ('zh' or 'en') - kept for API compatibility

    Returns:
        bool: True if learning sheet keywords detected
    """
    # language parameter kept for API compatibility but not used
    del language

    learning_sheet_keywords = ['半成品', '学习单']
    is_learning_sheet = any(keyword in user_prompt for keyword in learning_sheet_keywords)

    if is_learning_sheet:
        logger.debug("Learning sheet detected in prompt: '%s'", user_prompt)

    return is_learning_sheet


def _clean_prompt_for_learning_sheet(user_prompt: str) -> str:
    """
    Remove learning sheet keywords from prompt so LLM generates actual content.

    When user asks for "生成鸦片战争的半成品流程图" or "生成鸦片战争的流程图半成品",
    we want the LLM to generate content about "生成鸦片战争的流程图" (the actual topic),
    not meta-content about how to create learning sheets.

    Args:
        user_prompt: Original user prompt

    Returns:
        str: Cleaned prompt with learning sheet keywords removed
    """
    learning_sheet_keywords = ['半成品', '学习单']

    cleaned_prompt = user_prompt
    for keyword in learning_sheet_keywords:
        cleaned_prompt = cleaned_prompt.replace(keyword, '').strip()

    # Clean up any extra whitespace or punctuation left behind
    cleaned_prompt = re.sub(r'\s+', ' ', cleaned_prompt)  # Multiple spaces -> single space
    cleaned_prompt = re.sub(r'的图+$', '的', cleaned_prompt)  # "的图" at end -> "的" (for cases like "流程图的半成品图" -> "流程图的")
    cleaned_prompt = re.sub(r'的+$', '', cleaned_prompt)  # Remove trailing "的"
    cleaned_prompt = cleaned_prompt.strip()

    logger.debug("Cleaned prompt: '%s' -> '%s'", user_prompt, cleaned_prompt)
    return cleaned_prompt
