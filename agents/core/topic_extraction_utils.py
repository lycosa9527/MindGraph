"""
Topic extraction utilities for comparison diagrams.

This module provides functions to extract and parse topics from user prompts
and LLM responses for double bubble maps and other comparison diagrams.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Tuple
import logging
import re
import json

logger = logging.getLogger(__name__)


def parse_topic_extraction_result(
    result: str, language: str = 'zh'
) -> Tuple[str, str]:
    """
    Parse the result from topic extraction agent.

    Args:
        result (str): Raw result from the agent
        language (str): Language context ('zh' or 'en')

    Returns:
        tuple: (topic1, topic2) extracted topics
    """
    # Clean up the result
    topics = result.strip()

    # Handle case where LLM returns a complete JSON block
    if topics.startswith("```json"):
        json_topics = _extract_topics_from_json(topics)
        if json_topics:
            return json_topics

    # Try to extract topics from LLM response
    parsed_topics = _extract_topics_from_text(topics, language)
    if parsed_topics:
        return parsed_topics

    # If parsing completely failed, use fallback
    logger.debug("Topic extraction parsing failed, using fallback")
    return extract_topics_from_prompt(topics)


def _extract_topics_from_json(topics: str) -> Optional[Tuple[str, str]]:
    """
    Extract topics from JSON format.

    Args:
        topics: Text containing JSON format topics

    Returns:
        Tuple of (topic1, topic2) or None if extraction fails
    """
    json_match = re.search(r'```json\s*\n(.*?)\n```', topics, re.DOTALL)
    if json_match:
        json_content = json_match.group(1).strip()
        try:
            data = json.loads(json_content)
            if 'left' in data and 'right' in data:
                left_topic = data['left'].strip()
                right_topic = data['right'].strip()
                if left_topic != "A" and right_topic != "B":
                    return left_topic, right_topic
        except json.JSONDecodeError:
            pass
    return None


def _extract_topics_from_text(topics: str, language: str) -> Optional[Tuple[str, str]]:
    """
    Extract topics from text using language-specific separators.

    Args:
        topics: Text containing topics
        language: Language ('zh' or 'en')

    Returns:
        Tuple of (topic1, topic2) or None if extraction fails
    """
    if language == 'zh':
        # Handle Chinese "和" separator
        if "和" in topics:
            parts = topics.split("和")
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()

        # For Chinese, extract Chinese characters
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', topics)
        if len(chinese_words) >= 2:
            return chinese_words[0], chinese_words[1]
    else:
        # Handle English " and " separator
        if " and " in topics:
            parts = topics.split(" and ")
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()

        # For English, extract English words
        words = re.findall(r'\b\w+\b', topics)
        if len(words) >= 2:
            return words[0], words[1]

    return None


def extract_topics_from_prompt(user_prompt: str) -> Tuple[str, str]:
    """
    Extract two topics from the original user prompt using fallback logic.

    Args:
        user_prompt (str): User's input prompt

    Returns:
        tuple: (topic1, topic2) extracted topics
    """
    is_zh = any('\u4e00' <= ch <= '\u9fff' for ch in user_prompt)

    if is_zh:
        # For Chinese prompts
        # Look for specific car brands and other topics
        car_brands = ['宝马', '奔驰', '奥迪', '大众', '丰田', '本田', '福特', '雪佛兰']
        found_brands = []
        for brand in car_brands:
            if brand in user_prompt:
                found_brands.append(brand)

        if len(found_brands) >= 2:
            return found_brands[0], found_brands[1]

        # For Chinese prompts - use generic character extraction
        # Fallback: extract individual Chinese characters (2-4 characters each)
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', user_prompt)
        if len(chinese_words) >= 2:
            return chinese_words[0], chinese_words[1]
    else:
        # For English prompts - use generic word extraction
        # Fallback: extract any two distinct words, but filter out common verbs and prepositions
        common_words_to_skip = [
            'compare', 'and', 'or', 'the', 'a', 'an', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must',
            'shall', 'about', 'with', 'for', 'to', 'of', 'in', 'on', 'at', 'by',
            'from', 'up', 'down', 'out', 'off', 'over', 'under', 'between',
            'among', 'through', 'during', 'before', 'after', 'since', 'until',
            'while', 'when', 'where', 'why', 'how', 'what', 'which', 'who',
            'whom', 'whose'
        ]
        words = re.findall(r'\b\w+\b', user_prompt.lower())
        filtered_words = [
            word for word in words
            if word not in common_words_to_skip and len(word) > 2
        ]
        if len(filtered_words) >= 2:
            return filtered_words[0], filtered_words[1]

    # Final fallback
    return "Topic A", "Topic B"


def extract_topics_with_agent(
    user_prompt: str, language: str = 'zh'
) -> Tuple[str, str]:
    """
    Use LangChain agent to extract two topics for comparison.

    Args:
        user_prompt (str): User's input prompt
        language (str): Language for processing ('zh' or 'en')

    Returns:
        tuple: (topic1, topic2) extracted topics

    Raises:
        ValueError: If user_prompt is empty or invalid
    """
    # Input validation - raise error instead of using fallback placeholder
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        logger.error("Invalid user_prompt provided - empty or not a string")
        raise ValueError("user_prompt cannot be empty")

    if not isinstance(language, str) or language not in ['zh', 'en']:
        logger.warning("Invalid language '%s', defaulting to 'zh'", language)
        language = 'zh'

    logger.debug("Agent: Extracting topics from prompt: %s", user_prompt)
    # Create the topic extraction function
    from .prompt_helpers import create_topic_extraction_chain  # pylint: disable=import-outside-toplevel
    topic_func = create_topic_extraction_chain(language)
    try:
        # Run the function directly (not a LangChain chain)
        result = topic_func(user_prompt)
        logger.debug("Agent: Topic extraction result: %s", result)
        # Parse the result using utility function
        topics = parse_topic_extraction_result(result, language)
        return topics
    except Exception as e:
        logger.error("Agent: Topic extraction failed: %s", e)
        # Fallback to utility function
        return extract_topics_from_prompt(user_prompt)
