"""
Topic extraction functions.

This module provides functions for extracting topics from user prompts using LLM.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging

from agents.core.llm_clients import llm_classification

logger = logging.getLogger(__name__)


def extract_central_topic_llm(user_prompt: str, language: str = 'zh') -> str:
    """
    Extract central topic using LLM instead of hardcoded string manipulation.
    This provides better semantic understanding and context preservation.
    """
    try:
        if language == 'zh':
            prompt = f"从以下用户输入中提取核心主题，只返回主题内容，不要其他文字：\n{user_prompt}"
        else:
            prompt = f"Extract the central topic from this user input, return only the topic:\n{user_prompt}"

        result = llm_classification.invoke(prompt)
        # Clean up the result - remove any extra whitespace or formatting
        if not isinstance(result, str):
            result = str(result)
        central_topic = result.strip()

        # Fallback to original prompt if extraction fails
        if not central_topic or len(central_topic) < 2:
            logger.warning(
                "LLM topic extraction failed, using original prompt: %s",
                user_prompt
            )
            central_topic = user_prompt.strip()

        return central_topic

    except Exception as e:  # pylint: disable=broad-except
        logger.error("LLM topic extraction error: %s, using original prompt", e)
        return user_prompt.strip()


async def extract_double_bubble_topics_llm(user_prompt: str, language: str = 'zh', model: str = 'qwen') -> str:
    """
    Extract two topics for double bubble map comparison using LLM.
    This is specialized for double bubble maps that need two separate topics.
    Fully async - no event loop wrappers.
    """
    from services.llm import llm_service

    try:
        if language == 'zh':
            prompt = f"""从以下用户输入中提取两个要比较的主题，只返回两个主题，用"和"连接，不要其他文字：
{user_prompt}

重要：忽略动作词如"生成"、"创建"、"比较"、"制作"等，只提取实际要比较的两个主题。

示例：
输入："生成速度和加速度的双气泡图" → 输出："速度和加速度"
输入："比较苹果和橙子" → 输出："苹果和橙子"
输入："创建关于猫和狗的比较图" → 输出："猫和狗"
输入："制作一个关于太阳和月亮的对比图" → 输出："太阳和月亮"

你的输出："""
        else:
            prompt = f"""Extract two topics for comparison from this user input, \
return only the two topics separated by "and", no other text:
{user_prompt}

Examples:
Input: "generate a double bubble map about speed and acceleration" → Output: "speed and acceleration"
Input: "compare apples and oranges" → Output: "apples and oranges"
Input: "create a comparison chart about cats and dogs" → Output: "cats and dogs"

Your output:"""

        result = await llm_service.chat(
            prompt=prompt,
            model=model,
            max_tokens=100,
            temperature=0.3
        )

        # Clean up the result - remove any extra whitespace or formatting
        topics = result.strip()

        # Fallback to original prompt if extraction fails
        if not topics or len(topics) < 3:
            logger.warning(
                "LLM double bubble topic extraction failed, using original prompt: %s",
                user_prompt
            )
            topics = user_prompt.strip()

        return topics

    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "LLM double bubble topic extraction error: %s, using original prompt", e
        )
        return user_prompt.strip()


def extract_topics_and_styles_from_prompt_qwen(user_prompt: str, language: str = 'en') -> dict:
    """
    Simple replacement for the removed complex style extraction function.
    Returns minimal data structure that existing code expects.
    Now uses LLM-based topic extraction instead of hardcoded string manipulation.
    """
    # Use LLM-based topic extraction
    central_topic = extract_central_topic_llm(user_prompt, language)

    return {
        "topics": [central_topic] if central_topic else [],
        "style_preferences": {},
        "diagram_type": "bubble_map",  # Default
        "suggested_diagram_type": "concept_map"
    }
