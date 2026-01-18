"""
Characteristics generation utilities for double bubble maps.

This module provides functions to generate and parse characteristics
for comparison diagrams.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any
import logging
import re
import json
import yaml

from config.characteristics_fallbacks import (
    get_fallback_characteristics,
    get_default_fallback
)

logger = logging.getLogger(__name__)


def generate_characteristics_with_agent(
    topic1: str, topic2: str, language: str = 'zh'
) -> Dict[str, Any]:
    """
    Use LangChain agent to generate characteristics for double bubble map.

    Args:
        topic1 (str): First topic
        topic2 (str): Second topic
        language (str): Language for processing ('zh' or 'en')

    Returns:
        dict: Characteristics specification

    Raises:
        ValueError: If topic1 or topic2 is empty or invalid
    """
    # Input validation - raise error instead of using placeholder
    if not isinstance(topic1, str) or not topic1.strip():
        logger.error("Invalid topic1 provided - empty or not a string")
        raise ValueError("topic1 cannot be empty")

    if not isinstance(topic2, str) or not topic2.strip():
        logger.error("Invalid topic2 provided - empty or not a string")
        raise ValueError("topic2 cannot be empty")

    if not isinstance(language, str) or language not in ['zh', 'en']:
        logger.warning("Invalid language '%s', defaulting to 'zh'", language)
        language = 'zh'

    logger.debug("Agent: Generating characteristics for %s vs %s", topic1, topic2)
    # Create the characteristics generation function
    from .prompt_helpers import create_characteristics_chain  # pylint: disable=import-outside-toplevel
    char_func = create_characteristics_chain(language)
    try:
        # Run the function directly (not a LangChain chain)
        result = char_func(topic1, topic2)
        logger.debug("Agent: Characteristics generation result: %s", result)
        # Parse the result using utility function
        spec = parse_characteristics_result(result, topic1, topic2)
        return spec
    except Exception as e:
        logger.error("Agent: Characteristics generation failed: %s", e)
        # Fallback to utility function
        return generate_characteristics_fallback(topic1, topic2)


def parse_characteristics_result(
    result: str, _topic1: str, _topic2: str
) -> Dict[str, Any]:
    """
    Parse the result from characteristics generation agent.

    Args:
        result (str): Raw result from the agent
        _topic1 (str): First topic (unused, kept for API compatibility)
        _topic2 (str): Second topic (unused, kept for API compatibility)

    Returns:
        dict: Parsed characteristics specification
    """
    # Extract YAML from the result
    text = result.strip()

    # Handle case where LLM returns a complete JSON block
    if text.startswith("```json"):
        # Extract the content between ```json and ```
        json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            try:
                data = json.loads(json_content)
                # Convert JSON to YAML format for processing
                text = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            except json.JSONDecodeError:
                # Fallback: remove json markers
                text = text.replace("```json", "").replace("```", "").strip()
    else:
        # Remove any code block markers
        if text.startswith("```yaml"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        text = text.strip('`\n ')

    # Clean up any remaining template placeholders
    # Ensure text is a string before processing
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    text = _clean_template_placeholders(text)

    # Parse YAML
    try:
        spec = yaml.safe_load(text)
        logger.debug("After YAML load, spec type: %s, value: %s", type(spec), spec)
        if not isinstance(spec, dict):
            raise yaml.YAMLError("YAML parsing did not return a dict")
        if spec is None:
            raise yaml.YAMLError("YAML parsing returned None")
    except yaml.YAMLError as e:
        logger.error("YAML parsing error: %s", e)
        logger.error("Raw text: %s", text)
        # Try to extract just the lists
        spec = _extract_characteristics_from_text(text)

    # Validate and ensure all required fields exist
    spec = _validate_and_fill_characteristics(spec)

    # Check if we got meaningful content (not just template placeholders)
    if not _has_meaningful_content(spec):
        raise ValueError("No meaningful content generated, using fallback")

    return spec


def _clean_template_placeholders(text: str) -> str:
    """Clean up template placeholders in text."""
    if not isinstance(text, str):
        text = str(text)

    text = text.replace('"trait1"', '"Common trait"')
    text = text.replace('"feature1"', '"Unique feature"')
    text = text.replace('"特征1"', '"共同特征"')
    text = text.replace('"特点1"', '"独特特点"')

    return text


def _extract_characteristics_from_text(text: str) -> Dict[str, list]:
    """
    Extract characteristics from text when YAML parsing fails.

    Args:
        text: Raw text containing characteristics

    Returns:
        Dictionary with similarities, left_differences, right_differences
    """
    spec = {"similarities": [], "left_differences": [], "right_differences": []}
    text_str = str(text)
    lines = text_str.split('\n')
    current_key = None
    for line in lines:
        line = line.strip()
        if line.startswith('similarities:'):
            current_key = 'similarities'
        elif line.startswith('left_differences:'):
            current_key = 'left_differences'
        elif line.startswith('right_differences:'):
            current_key = 'right_differences'
        elif line.startswith('- ') and current_key:
            item = line[2:].strip().strip('"')
            if item and not item.startswith('trait') and not item.startswith('feature'):
                spec[current_key].append(item)

    return spec


def _validate_and_fill_characteristics(spec: Dict[str, Any]) -> Dict[str, list]:
    """
    Validate and fill missing characteristics fields.

    Args:
        spec: Characteristics specification dictionary

    Returns:
        Validated and filled specification
    """
    if not spec.get('similarities') or len(spec.get('similarities', [])) < 2:
        spec['similarities'] = ["Comparable"]
    if not spec.get('left_differences') or len(spec.get('left_differences', [])) < 2:
        spec['left_differences'] = ["Unique"]
    if not spec.get('right_differences') or len(spec.get('right_differences', [])) < 2:
        spec['right_differences'] = ["Unique"]

    return spec


def _has_meaningful_content(spec: Dict[str, Any]) -> bool:
    """
    Check if characteristics contain meaningful content.

    Args:
        spec: Characteristics specification dictionary

    Returns:
        True if meaningful content exists, False otherwise
    """
    placeholders = ['trait', 'feature', '特征', '特点', 'comparable', 'unique']
    for key in ['similarities', 'left_differences', 'right_differences']:
        for item in spec.get(key, []):
            if not any(placeholder in str(item).lower() for placeholder in placeholders):
                return True
    return False


def generate_characteristics_fallback(topic1: str, topic2: str) -> Dict[str, Any]:
    """
    Generate fallback characteristics when agent fails.

    Args:
        topic1 (str): First topic
        topic2 (str): Second topic

    Returns:
        dict: Fallback characteristics specification
    """
    # Try to get specific fallback
    fallback = get_fallback_characteristics(topic1, topic2)
    if fallback:
        return fallback

    # Use default fallback
    return get_default_fallback()
