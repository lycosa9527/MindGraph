"""
Utility functions for agent operations.

This module provides shared utility functions for error handling, validation,
and JSON parsing used across the agent system.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import json
import re
import time
import logging

logger = logging.getLogger(__name__)


def create_error_response(message: str, error_type: str = "generation", context: dict | None = None) -> dict:
    """
    Create standardized error response format.

    Args:
        message: Error message
        error_type: Type of error (generation, validation, classification, etc.)
        context: Additional context information

    Returns:
        dict: Standardized error response
    """
    error_response = {
        "error": message,
        "error_type": error_type,
        "timestamp": time.time()
    }

    if context:
        error_response["context"] = context

    return error_response


def validate_inputs(user_prompt: str, language: str) -> None:
    """
    Validate input parameters for agent functions.

    Args:
        user_prompt: User input prompt
        language: Language code

    Raises:
        ValueError: If inputs are invalid
    """
    if not user_prompt or not isinstance(user_prompt, str) or not user_prompt.strip():
        raise ValueError("User prompt cannot be empty or None")

    if len(user_prompt.strip()) > 10000:  # Reasonable limit
        raise ValueError("User prompt too long (max 10,000 characters)")

    if not language or language not in ['zh', 'en']:
        raise ValueError("Language must be 'zh' or 'en'")


def _salvage_json_string(raw: str) -> str:
    """Attempt to salvage a JSON object from messy LLM output."""
    if not raw:
        return ""
    s = raw.strip().strip('`')
    # Remove code fences if present
    if s.startswith('```'):
        fence_end = s.rfind('```')
        if fence_end > 3:
            s = s[3:fence_end]
    # Find first '{' and balance braces outside strings
    start = s.find('{')
    if start == -1:
        return ""
    buf = []
    depth = 0
    in_str = False
    esc = False
    for ch in s[start:]:
        buf.append(ch)
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
    candidate = ''.join(buf)
    while depth > 0:
        candidate += '}'
        depth -= 1
    # Remove trailing commas before } or ]
    candidate = re.sub(r',\s*(\]|\})', r'\1', candidate)
    return candidate.strip()


def extract_yaml_from_code_block(text: str | None) -> str:
    """Extract content from fenced code blocks, robust to minor formatting.

    - Handles ```json, ```yaml, ```yml, ```js, or bare ```
    - Closing fence may or may not be preceded by a newline
    - If multiple blocks exist, returns the first
    - If no fences are found, returns stripped text
    """
    s = (text or "").strip()
    # Regex-based extraction first
    match = re.search(r"```(?:json|yaml|yml|javascript|js)?\s*\r?\n([\s\S]*?)\r?\n?```", s, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: manual slicing if starts with a fence but regex failed
    if s.startswith("```"):
        # Drop first line (```lang)
        first_nl = s.find("\n")
        content = s[first_nl + 1:] if first_nl != -1 else s[3:]
        last_fence = content.rfind("```")
        if last_fence != -1:
            content = content[:last_fence]
        return content.strip()

    return s


def _salvage_truncated_json(text: str) -> str | None:
    """Aggressively salvage truncated JSON by completing incomplete strings and structures."""
    try:
        # Find the last complete relationship entry
        lines = text.split('\n')
        salvaged_lines = []
        in_relationships = False
        brace_count = 0

        for line in lines:
            if '"relationships"' in line:
                in_relationships = True
                salvaged_lines.append(line)
                continue

            if in_relationships:
                # Count braces to track structure
                brace_count += line.count('{') - line.count('}')

                # Check if this line is complete (ends with } or ,)
                if line.strip().endswith('},') or line.strip().endswith('}'):
                    salvaged_lines.append(line)
                elif line.strip().endswith(','):
                    salvaged_lines.append(line)
                elif '"from"' in line and '"to"' in line and '"label"' in line:
                    # This looks like a complete relationship, add it
                    if not line.strip().endswith(','):
                        line = line.rstrip() + ','
                    salvaged_lines.append(line)
                elif (line.strip().startswith('"from"') or
                      line.strip().startswith('"to"') or
                      line.strip().startswith('"label"')):
                    # This is part of a relationship, try to complete it
                    if '"from"' in line and '"to"' in line and '"label"' in line:
                        # Looks complete, add comma if needed
                        if not line.strip().endswith(','):
                            line = line.rstrip() + ','
                        salvaged_lines.append(line)
                    else:
                        # Incomplete, skip this line
                        continue
                else:
                    salvaged_lines.append(line)
            else:
                salvaged_lines.append(line)

        # Close the relationships array and main object
        if in_relationships:
            # Remove trailing comma from last relationship
            if salvaged_lines and salvaged_lines[-1].strip().endswith(','):
                salvaged_lines[-1] = salvaged_lines[-1].rstrip(',')

            # Add closing brackets
            salvaged_lines.append('  ]')
            salvaged_lines.append('}')

        salvaged_text = '\n'.join(salvaged_lines)

        # Validate the salvaged JSON
        json.loads(salvaged_text)
        return salvaged_text

    except Exception as e:  # pylint: disable=broad-except
        logger.error("JSON salvage failed: %s", e)
        return None


def _parse_strict_json(text: str) -> dict:
    """Parse JSON with robust extraction and salvage; raise on failure."""
    cleaned = extract_yaml_from_code_block(text)
    if not cleaned:
        raise ValueError("Failed to extract content from text")
    # Normalize unicode quotes and remove non-JSON noise
    cleaned = cleaned.strip().strip('`')
    # Replace smart quotes with ASCII equivalents
    cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    cleaned = cleaned.replace('"', '"').replace('"', '"').replace('"', '"').replace('"', '"')
    # Remove zero-width and control characters
    cleaned = re.sub(r"[\u200B-\u200D\uFEFF]", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", cleaned)
    # Remove JS-style comments if present
    cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    # Remove trailing commas before ] or }
    cleaned = re.sub(r",\s*(\]|\})", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:  # pylint: disable=broad-except
        # Try salvage
        candidate = _salvage_json_string(cleaned)
        if candidate:
            candidate = re.sub(r",\s*(\]|\})", r"\1", candidate)
            return json.loads(candidate)
        raise
