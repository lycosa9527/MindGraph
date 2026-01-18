"""
JSON parsing and repair utilities for LLM responses.

This module provides functions to extract and repair JSON from LLM responses,
handling common formatting issues and structural problems.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Optional, Any
import json
import logging
import re

from dotenv import load_dotenv

# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)


def extract_json_from_response(
    response_content: Any, allow_partial: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM response content.

    Handles legitimate formatting issues:
    - Markdown code blocks (```json ... ```)
    - Unicode quote characters (smart quotes)
    - Trailing commas (common JSON extension)
    - Basic whitespace/control characters

    If JSON is invalid and allow_partial=True, attempts to extract valid branches
    from corrupted JSON (for mind maps and similar structures).

    Args:
        response_content (str): Raw response content from LLM
        allow_partial (bool): If True, attempt partial recovery when JSON is invalid

    Returns:
        dict or None: Extracted JSON data or None if failed
        If allow_partial=True and partial recovery succeeds, returns dict with
        '_partial_recovery' key set to True and '_recovery_warnings' list
    """
    if not response_content:
        logger.warning("Empty response content provided")
        return None

    try:
        content = str(response_content).strip()

        # Extract JSON content - try markdown blocks first, then direct content
        json_content = _extract_json_content(content)

        if not json_content:
            return _handle_no_json_content(content)

        # Clean legitimate formatting issues (not structural problems)
        cleaned = _clean_json_string(json_content)

        # Try to parse - if it fails, attempt repair
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            return _handle_json_decode_error(
                cleaned, e, allow_partial
            )

    except Exception as e:
        # Unexpected error - log with full context
        content_str = str(response_content)
        content_preview = (
            content_str[:500] + "..." if len(content_str) > 500 else content_str
        )
        logger.error(
            "Unexpected error extracting JSON: %s. Content preview: %s",
            e,
            content_preview,
            exc_info=True
        )
        return None


def _extract_json_content(content: str) -> Optional[str]:
    """
    Extract JSON content from response, handling markdown blocks and direct content.

    Args:
        content: Raw response content

    Returns:
        Extracted JSON content string or None
    """
    # Check for markdown code blocks
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    # Find the root JSON object by finding the first { and matching its closing }
    first_brace = content.find('{')
    if first_brace != -1:
        json_content = _extract_balanced_json_object(content, first_brace)
        if json_content:
            return json_content

        # Fallback: try to find JSON object or array patterns
        return _extract_json_fallback(content, first_brace)
    else:
        # No opening brace found, try array pattern
        arr_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', content, re.DOTALL)
        if arr_match:
            return arr_match.group(0)

    return None


def _extract_balanced_json_object(content: str, first_brace: int) -> Optional[str]:
    """
    Extract JSON object using balanced bracket matching.

    Args:
        content: Full content string
        first_brace: Position of first opening brace

    Returns:
        Extracted JSON object string or None
    """
    brace_count = 0
    json_end = first_brace
    in_string = False
    escape_next = False

    for i in range(first_brace, len(content)):
        char = content[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        # Track string state using regular quotes only
        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    return content[first_brace:json_end]

    # If balanced matching failed, try to find the largest complete JSON object
    if brace_count != 0:
        last_brace = content.rfind('}')
        if last_brace > first_brace:
            candidate = content[first_brace:last_brace + 1]
            # Quick validation: check if it has root-level fields we expect
            if '"whole"' in candidate or '"topic"' in candidate or '"dimension"' in candidate:
                return candidate

    return None


def _extract_json_fallback(content: str, first_brace: int) -> Optional[str]:  # pylint: disable=unused-argument
    """
    Fallback JSON extraction using regex patterns.

    Args:
        content: Full content string
        first_brace: Position of first opening brace (unused, kept for API consistency)

    Returns:
        Extracted JSON content string or None
    """
    obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    arr_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', content, re.DOTALL)

    if obj_match:
        return obj_match.group(0)
    if arr_match:
        return arr_match.group(0)

    # Last fallback: try greedy match for { ... }
    greedy_match = re.search(r'\{.*\}', content, re.DOTALL)
    if greedy_match:
        return greedy_match.group(0)

    return None


def _handle_no_json_content(content: str) -> Optional[Dict[str, Any]]:
    """
    Handle case where no JSON content is found.

    Args:
        content: Full content string

    Returns:
        Error dict if non-JSON response detected, None otherwise
    """
    content_preview = content[:500] + "..." if len(content) > 500 else content

    # Detect non-JSON responses (LLM asking for more information)
    non_json_patterns = [
        r'请你提供',  # "Please provide"
        r'请你补充',  # "Please supplement/add"
        r'这样我就能',  # "so I can"
        r'Please provide',
        r'Please.*more.*information',
        r'so I can',
        r'需要.*信息',  # "need information"
        r'告知.*信息',  # "inform about information"
    ]

    for pattern in non_json_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            logger.warning(
                "Detected non-JSON response (LLM asking for more info): "
                "Pattern '%s' matched. Content preview: %s",
                pattern,
                content_preview
            )
            # Return structured error instead of None to allow retry logic
            return {
                '_error': 'non_json_response',
                '_content': content,
                '_type': 'llm_requesting_info'
            }

    logger.error(
        "Failed to extract JSON: No JSON structure found in response. Content: %s",
        content_preview
    )
    return None


def _handle_json_decode_error(
    cleaned: str,
    error: json.JSONDecodeError,
    allow_partial: bool
) -> Optional[Dict[str, Any]]:
    """
    Handle JSON decode errors by attempting repair and partial recovery.

    Args:
        cleaned: Cleaned JSON string that failed to parse
        error: JSONDecodeError exception
        allow_partial: Whether to attempt partial recovery

    Returns:
        Parsed JSON dict if repair/recovery succeeded, None otherwise
    """
    error_pos = getattr(error, 'pos', None)
    error_msg = str(error)
    content_preview = cleaned[:500] + "..." if len(cleaned) > 500 else cleaned

    logger.debug(
        "Initial JSON parse failed: %s (position: %s). Attempting repair...",
        error_msg,
        error_pos
    )

    # Attempt to repair common structural issues
    error_pos_int = error_pos if error_pos is not None else 0
    repaired = _repair_json_structure(cleaned, error_pos_int)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e2:
            logger.debug("Repaired JSON still invalid: %s. Original error: %s", e2, error_msg)

    # If repair failed and partial recovery is allowed, try to extract valid branches
    if allow_partial:
        partial_result = _extract_partial_json(cleaned)
        if partial_result:
            logger.warning(
                "Partial JSON recovery succeeded. Original error: %s (position: %s). "
                "Recovered %s valid branches.",
                error_msg,
                error_pos,
                partial_result.get('_recovered_count', 0)
            )
            return partial_result

    # If repair failed, log the error with context
    logger.error(
        "Failed to parse JSON: %s (position: %s). Content preview: %s",
        error_msg,
        error_pos,
        content_preview
    )
    return None


def _extract_partial_json(text: str) -> Optional[Dict]:
    """
    Extract valid branches from corrupted JSON when full parsing fails.

    This function attempts to salvage valid data structures from malformed JSON,
    specifically designed for mind maps and similar tree structures where we have:
    - A root object with 'topic' and 'children' fields
    - Children array containing branch objects with 'id', 'label', and 'children' fields

    Strategy:
    1. Extract the topic if present
    2. Find all complete branch objects in the children array
    3. Build a valid JSON structure with only the complete branches
    4. Return partial result with warning flags

    Args:
        text: Corrupted JSON text

    Returns:
        dict with partial data and recovery metadata, or None if extraction failed
    """
    if not text:
        return None

    warnings = []
    recovered_branches = []

    try:
        # Step 1: Try to extract topic
        topic = _extract_topic_from_text(text)

        # Step 2: Find all complete branch objects
        children_start = text.find('"children"')
        if children_start == -1:
            children_start = text.find("'children'")

        if children_start != -1:
            array_start = text.find('[', children_start)
            if array_start != -1:
                recovered_branches = _extract_branches_from_array(
                    text[array_start:]
                )

        # Step 3: Build result structure
        if not topic and not recovered_branches:
            return None  # Nothing recoverable

        result = {}
        if topic:
            result["topic"] = topic
        else:
            result["topic"] = "Untitled"  # Fallback topic
            warnings.append("Topic not found, using fallback")

        if recovered_branches:
            result["children"] = recovered_branches
        else:
            result["children"] = []
            warnings.append("No valid branches recovered")

        # Add recovery metadata
        result["_partial_recovery"] = True
        result["_recovery_warnings"] = warnings
        result["_recovered_count"] = len(recovered_branches)

        logger.info(
            "Partial JSON recovery: extracted %s branches, %s warnings",
            len(recovered_branches),
            len(warnings)
        )
        return result

    except Exception as e:
        logger.debug("Partial JSON extraction failed: %s", e)
        return None


def _extract_topic_from_text(text: str) -> Optional[str]:
    """Extract topic from JSON text."""
    topic_match = re.search(r'"topic"\s*:\s*"([^"]+)"', text)
    topic = topic_match.group(1) if topic_match else None

    if not topic:
        # Try alternative patterns
        topic_match = re.search(r'"topic"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', text)
        if topic_match:
            topic = topic_match.group(1).replace('\\"', '"').replace('\\n', '\n')

    return topic


def _extract_branches_from_array(array_text: str) -> list:
    """
    Extract branch objects from children array.

    Args:
        array_text: Text starting from children array

    Returns:
        List of recovered branch objects
    """
    recovered_branches = []

    # Pattern 1: Mind map format with "label"
    branch_pattern_label = (
        r'\{\s*"id"\s*:\s*"([^"]+)"\s*,\s*"label"\s*:\s*"([^"]*(?:\\.[^"]*)*)"[^}]*\}'
    )
    # Pattern 2: Tree map format with "text"
    branch_pattern_text = (
        r'\{\s*"id"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"([^"]*(?:\\.[^"]*)*)"[^}]*\}'
    )
    # Pattern 3: Tree map format without id (just "text")
    branch_pattern_text_no_id = r'\{\s*"text"\s*:\s*"([^"]*(?:\\.[^"]*)*)"[^}]*\}'

    # Try mind map pattern first
    for match in re.finditer(branch_pattern_label, array_text, re.DOTALL):
        branch_obj = _build_mind_map_branch(match)
        if branch_obj:
            recovered_branches.append(branch_obj)

    # Try tree map pattern with id
    for match in re.finditer(branch_pattern_text, array_text, re.DOTALL):
        branch_obj = _build_tree_map_branch_with_id(match)
        if branch_obj:
            recovered_branches.append(branch_obj)

    # Try tree map pattern without id
    for match in re.finditer(branch_pattern_text_no_id, array_text, re.DOTALL):
        branch_obj = _build_tree_map_branch_no_id(match)
        if branch_obj:
            recovered_branches.append(branch_obj)

    return recovered_branches


def _build_mind_map_branch(match: re.Match) -> Optional[Dict]:
    """Build mind map branch object from regex match."""
    try:
        branch_text = match.group(0)
        branch_id = match.group(1)
        branch_label = match.group(2).replace('\\"', '"').replace('\\n', '\n')

        children_list = _extract_children_from_branch(branch_text, 'label')
        branch_obj = {"id": branch_id, "label": branch_label}
        if children_list:
            branch_obj["children"] = children_list

        return branch_obj
    except Exception as e:
        logger.debug("Skipping invalid branch object: %s", e)
        return None


def _build_tree_map_branch_with_id(match: re.Match) -> Optional[Dict]:
    """Build tree map branch object with id from regex match."""
    try:
        branch_text = match.group(0)
        branch_id = match.group(1)
        branch_text_value = match.group(2).replace('\\"', '"').replace('\\n', '\n')

        children_list = _extract_children_from_branch(branch_text, 'text')
        branch_obj = {"id": branch_id, "text": branch_text_value}
        if children_list:
            branch_obj["children"] = children_list

        return branch_obj
    except Exception as e:
        logger.debug("Skipping invalid branch object: %s", e)
        return None


def _build_tree_map_branch_no_id(match: re.Match) -> Optional[Dict]:
    """Build tree map branch object without id from regex match."""
    try:
        branch_text = match.group(0)
        branch_text_value = match.group(1).replace('\\"', '"').replace('\\n', '\n')

        children_list = _extract_children_from_branch(branch_text, 'text')
        branch_id = branch_text_value.lower().replace(' ', '-')[:20]
        branch_obj = {"id": branch_id, "text": branch_text_value}
        if children_list:
            branch_obj["children"] = children_list

        return branch_obj
    except Exception as e:
        logger.debug("Skipping invalid branch object: %s", e)
        return None


def _extract_children_from_branch(branch_text: str, field_name: str) -> list:
    """
    Extract children from branch object.

    Args:
        branch_text: Branch object text
        field_name: Field name ('label' or 'text')

    Returns:
        List of child objects
    """
    children_list = []
    children_match = re.search(r'"children"\s*:\s*\[(.*?)\]', branch_text, re.DOTALL)

    if children_match:
        children_content = children_match.group(1)
        if field_name == 'label':
            child_pattern = (
                r'\{\s*"id"\s*:\s*"([^"]+)"\s*,\s*"label"\s*:\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            )
            for child_match in re.finditer(child_pattern, children_content):
                child_id = child_match.group(1)
                child_label = child_match.group(2).replace('\\"', '"').replace('\\n', '\n')
                children_list.append({"id": child_id, "label": child_label})
        else:  # field_name == 'text'
            child_pattern_with_id = (
                r'\{\s*"id"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            )
            child_pattern_text_only = r'\{\s*"text"\s*:\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'

            for child_match in re.finditer(child_pattern_with_id, children_content):
                child_id = child_match.group(1)
                child_text = child_match.group(2).replace('\\"', '"').replace('\\n', '\n')
                children_list.append({"id": child_id, "text": child_text})

            for child_match in re.finditer(child_pattern_text_only, children_content):
                child_text = child_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                child_id = child_text.lower().replace(' ', '-')[:20]
                children_list.append({"id": child_id, "text": child_text})

    return children_list


def _repair_json_structure(text: str, error_pos: Optional[int] = None) -> Optional[str]:
    """
    Attempt to repair common JSON structural issues from LLM responses.

    Handles:
    - Duplicate object entries (e.g., {"id": "x"        {"id": "x", "label": "y"})
    - Missing closing braces/commas
    - Incomplete objects in arrays
    - Missing commas between array elements or object properties

    Args:
        text: JSON text that failed to parse
        error_pos: Position where parsing failed (if available)

    Returns:
        Repaired JSON string, or None if repair not possible
    """
    if not text:
        return None

    repaired = text

    # Pattern 0: Fix duplicate keys in brace map structures
    repaired = _fix_duplicate_keys(repaired)

    # Pattern 0b-0e: Fix missing commas between objects
    repaired = _fix_missing_commas(repaired)

    # Pattern 1: Fix duplicate object entries
    repaired = _fix_duplicate_objects(repaired)

    # Pattern 2: Fix incomplete objects before different objects
    repaired = _fix_incomplete_objects_before_different(repaired)

    # Pattern 3: Fix incomplete object at end of array/object
    repaired = _fix_incomplete_objects_at_end(repaired)

    # Pattern 4: Remove consecutive duplicate complete objects
    repaired = _remove_consecutive_duplicates(repaired)

    # Pattern 5: Fix missing commas around error position
    if error_pos is not None:
        repaired = _fix_missing_commas_around_error(repaired, error_pos)

    return repaired if repaired != text else None


def _fix_duplicate_keys(text: str) -> str:
    """Fix duplicate keys in brace map structures."""
    # Pattern 0: Fix duplicate keys
    duplicate_key_pattern = r'\{"name":\s*"([^"]+)"\},\{"name":\s*"name":\s*"([^"]+)"\}'

    def fix_duplicate_key(match: re.Match[str]) -> str:
        first_value = match.group(1)
        second_value = match.group(2)
        return f'{{"name":"{first_value}"}},{{"name":"{second_value}"}}'

    text = re.sub(duplicate_key_pattern, fix_duplicate_key, text)

    # Pattern 0b: Fix {"name":"name":"value"} -> {"name":"value"}
    duplicate_name_key = r'\{"name":\s*"name":\s*"([^"]+)"\}'
    text = re.sub(duplicate_name_key, r'{"name":"\1"}', text)

    return text


def _fix_missing_commas(text: str) -> str:
    """Fix missing commas between objects."""
    # Pattern 0c: Fix missing colons in object structures (brace map specific)
    missing_comma_between_objects = r'\}\s*(?=\{"name":)'
    text = re.sub(missing_comma_between_objects, '},', text)

    # Pattern 0d: Fix missing commas between objects in arrays (general case)
    missing_comma_between_array_objects = r'\}\s*(?=\{"text":)'
    text = re.sub(missing_comma_between_array_objects, '},', text)

    # Pattern 0e: Fix missing commas between children array elements
    text = re.sub(r'\}\s*(?=\{"(?:text|id|label|name)":)', '},', text)

    return text


def _fix_duplicate_objects(text: str) -> str:
    """Fix duplicate object entries - incomplete object followed by complete duplicate."""
    incomplete_pattern = r'(\{"id":\s*"([^"]+)")\s+(?=\{)'
    matches = list(re.finditer(incomplete_pattern, text))

    if matches:
        # Process from end to preserve positions
        for match in reversed(matches):
            incomplete_start = match.start()
            incomplete_end = match.end()
            incomplete_id = match.group(2)
            incomplete_obj = match.group(1)

            # Check if the incomplete object is missing a closing brace
            if incomplete_obj.rstrip().endswith('}'):
                continue  # It's complete, skip

            # Find the next object starting after the incomplete one
            remaining_text = text[incomplete_end:]
            next_obj_match = re.search(r'(\{"id":\s*"([^"]+)"[^}]*\})', remaining_text)

            if next_obj_match:
                next_id = next_obj_match.group(2)
                # Check if it's a duplicate (same id)
                if incomplete_id == next_id:
                    # Found a complete duplicate - remove the incomplete one
                    text = text[:incomplete_start] + text[incomplete_end:]
                    logger.debug(
                        "Fixed duplicate object: removed incomplete object with id '%s'",
                        incomplete_id
                    )

    return text


def _fix_incomplete_objects_before_different(text: str) -> str:
    """Fix incomplete objects missing closing brace before next different object."""
    incomplete_before_different = (
        r'(\{"id":\s*"([^"]+)")\s+(?=\{"id":\s*"([^"]+)"[^}]*\})'
    )
    matches = list(re.finditer(incomplete_before_different, text))
    if matches:
        for match in reversed(matches):
            incomplete_id = match.group(2)
            next_id = match.group(3)
            # Only fix if IDs are different (not duplicates handled by Pattern 1)
            if incomplete_id != next_id:
                incomplete = match.group(1)
                if not incomplete.rstrip().endswith('}'):
                    # Close the incomplete object
                    fixed = incomplete.rstrip() + '},'
                    text = text[:match.start()] + fixed + text[match.end():]
                    logger.debug("Fixed incomplete object before different object")

    return text


def _fix_incomplete_objects_at_end(text: str) -> str:
    """Fix incomplete object at end of array/object."""
    incomplete_end_pattern = r'(\{"id":\s*"[^"]+")\s*([\]\}])'
    matches = list(re.finditer(incomplete_end_pattern, text))
    if matches:
        for match in reversed(matches):
            obj_start = match.group(1)
            closing = match.group(2)
            # Check if object is incomplete
            if not obj_start.rstrip().endswith('}'):
                fixed_obj = obj_start.rstrip() + '}'
                if closing == ']':
                    # In array context, check if we need a comma
                    before = text[:match.start()].rstrip()
                    if before and not before.endswith('[') and not before.endswith(','):
                        fixed_obj += ','
                text = text[:match.start()] + fixed_obj + closing + text[match.end():]
                logger.debug("Fixed incomplete object at end")

    return text


def _remove_consecutive_duplicates(text: str) -> str:
    """Remove consecutive duplicate complete objects."""
    consecutive_duplicate = (
        r'(\{"id":\s*"([^"]+)",\s*"[^"]+":\s*"[^"]+"[^}]*\})\s*,\s*\1'
    )
    return re.sub(consecutive_duplicate, r'\1', text)


def _fix_missing_commas_around_error(text: str, error_pos: int) -> str:
    """Fix missing commas around error position."""
    if error_pos >= len(text):
        return text

    # Look around the error position for missing commas
    start_check = max(0, error_pos - 50)
    end_check = min(len(text), error_pos + 50)
    error_context = text[start_check:end_check]

    # Look for } followed by whitespace and then { or [
    missing_comma_pattern = r'\}\s+(?=[\{\[])'
    if re.search(missing_comma_pattern, error_context):
        # Fix missing commas in the error context
        fixed_context = re.sub(r'\}\s+(?=\{)', '},', error_context)
        text = text[:start_check] + fixed_context + text[end_check:]
        logger.debug("Fixed missing comma around error position %s", error_pos)

    return text


def _remove_js_comments_safely(text: str) -> str:
    """
    Remove JavaScript-style comments from JSON, but only outside of string values.

    This function respects JSON string boundaries to avoid corrupting URLs,
    file paths, or other string values that contain // or /* */ sequences.

    Args:
        text: JSON text that may contain comments

    Returns:
        Text with comments removed, but string values preserved
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        if escape_next:
            # Escaped character - add as-is and reset escape flag
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == '\\':
            # Escape character - next char is escaped
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"':
            # Toggle string state
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            # Inside string - add character as-is
            result.append(char)
            i += 1
            continue

        # Outside string - check for comments
        if i < len(text) - 1 and text[i:i+2] == '//':
            # Single-line comment - skip until end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            # Keep the newline if present
            if i < len(text) and text[i] == '\n':
                result.append('\n')
                i += 1
        elif i < len(text) - 1 and text[i:i+2] == '/*':
            # Multi-line comment - skip until */
            i += 2
            while i < len(text):
                if i + 1 < len(text) and text[i:i+2] == '*/':
                    i += 2
                    break
                i += 1
        else:
            # Regular character - add as-is
            result.append(char)
            i += 1

    return ''.join(result)


def _escape_chinese_quotes_in_strings(text: str) -> str:
    """
    Escape Chinese quotation marks that appear inside JSON string values.

    Chinese quotation marks (" and ") break JSON parsing when they appear inside
    string values because the parser thinks the string has ended.

    This function identifies JSON string values and escapes Chinese quotes inside them.

    Args:
        text: JSON text that may contain Chinese quotes inside strings

    Returns:
        Text with Chinese quotes escaped inside string values
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        if escape_next:
            # Escaped character - add as-is and reset escape flag
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == '\\':
            # Escape character - next char is escaped
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"':
            # Toggle string state
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            # Inside string - escape Chinese quotation marks
            if char == '\u201c':  # Chinese left double quotation mark "
                result.append('\\"')
            elif char == '\u201d':  # Chinese right double quotation mark "
                result.append('\\"')
            else:
                result.append(char)
            i += 1
            continue

        # Outside string - add character as-is
        result.append(char)
        i += 1

    return ''.join(result)


def _clean_json_string(text: str) -> str:
    """
    Clean JSON string by fixing legitimate formatting issues.

    Only fixes issues that don't change JSON semantics:
    - Unicode quote normalization
    - Chinese quotation mark escaping inside strings
    - Control character removal
    - Trailing comma removal (common JSON extension)
    - JS-style comments (only outside string values)

    Does NOT attempt to fix structural problems (truncated JSON, missing brackets, etc.)

    Args:
        text: Raw JSON text to clean

    Returns:
        Cleaned text
    """
    # Remove markdown code block markers if still present
    text = re.sub(r'```(?:json)?\s*\n?', '', text)
    text = re.sub(r'```\s*\n?', '', text)

    # Remove leading/trailing whitespace and backticks
    text = text.strip().strip('`')

    # Escape Chinese quotation marks inside JSON strings FIRST (before other quote replacements)
    text = _escape_chinese_quotes_in_strings(text)

    # Replace smart quotes with ASCII equivalents (legitimate fix)
    # Note: We do this AFTER escaping Chinese quotes to avoid double-processing
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('"', '"').replace('"', '"')

    # Remove zero-width and control characters (legitimate fix)
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)

    # Remove JS-style comments (only outside string values to avoid corrupting URLs/paths)
    text = _remove_js_comments_safely(text)

    # Remove trailing commas before ] or } (common JSON extension, legitimate fix)
    text = re.sub(r',\s*(\]|\})', r'\1', text)

    return text.strip()
