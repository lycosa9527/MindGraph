"""
Shared helpers for user-specified fixed diagram structure (Case 2).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, List, Optional, Tuple

from utils.prompt_locale import is_chinese_prompt_shell_language


def normalize_label_list(values: Any) -> List[str]:
    """Return non-empty stripped strings from a list-like fixed_nodes value."""
    if not isinstance(values, list):
        return []
    labels: List[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            labels.append(text)
    return labels


def node_display_text(node: Any) -> str:
    """Extract display text from a diagram node dict."""
    if not isinstance(node, dict):
        return str(node).strip() if node is not None else ""
    for key in ("text", "name", "label"):
        value = node.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def extract_part_names(parts: Any) -> List[str]:
    """Extract top-level part/step/category names from heterogeneous LLM output."""
    if not isinstance(parts, list):
        return []
    if parts and all(isinstance(item, str) for item in parts):
        return normalize_label_list(parts)
    return [node_display_text(item) for item in parts if node_display_text(item)]


def validate_fixed_labels(
    actual: List[str],
    expected: List[str],
    item_name: str,
) -> Tuple[bool, str]:
    """Verify actual labels match expected count and order exactly."""
    if len(actual) != len(expected):
        return False, f"Expected {len(expected)} {item_name}, got {len(actual)}"
    for index, label in enumerate(expected):
        if index >= len(actual) or actual[index] != label:
            return False, f"{item_name.capitalize()} {index + 1} must be '{label}'"
    return True, ""


def append_fixed_labels_user_note(
    base_user_prompt: str,
    language: str,
    *,
    zh_intro: str,
    en_intro: str,
    labels: List[str],
) -> str:
    """Append an EXACT-label instruction block to the user message."""
    if not labels:
        return base_user_prompt
    joined = ", ".join(labels)
    if is_chinese_prompt_shell_language(language):
        return f"{base_user_prompt}\n\n{zh_intro}{joined}"
    return f"{base_user_prompt}\n\n{en_intro}{joined}"


def fixed_labels_from_nodes(
    fixed_nodes: Optional[dict],
    key: str,
) -> Optional[List[str]]:
    """Read normalized fixed labels from fixed_nodes when non-empty."""
    if not fixed_nodes:
        return None
    labels = normalize_label_list(fixed_nodes.get(key))
    return labels or None
