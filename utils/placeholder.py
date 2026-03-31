"""
Placeholder text detection for Node Palette and diagram generation.

Aligns with frontend useAutoComplete.ts placeholder patterns.
Used to filter out template/placeholder text before sending to LLM prompts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import re
from typing import Optional


# Chinese placeholder patterns (aligned with frontend useAutoComplete.ts)
_CHINESE_PLACEHOLDERS = [
    re.compile(r"^分支\s*\d+$"),
    re.compile(r"^子项\s*[\d.]+$"),
    re.compile(r"^子节点\s*[\d.]+$"),
    re.compile(r"^子\s*[\d.]+$"),
    re.compile(r"^新.*$"),
    re.compile(r"^属性\s*\d+$"),
    re.compile(r"^步骤\s*\d+$"),
    re.compile(r"^子步骤\s*[\d.]+$"),
    re.compile(r"^原因\s*\d+$"),
    re.compile(r"^结果\s*\d+$"),
    re.compile(r"^联想\s*\d+$"),
    re.compile(r"^事件流程$"),
    re.compile(r"^事件$"),
    re.compile(r"^主题\s*\d+$"),
    re.compile(r"^主题$"),
    re.compile(r"^主题[A-Z]$"),
    re.compile(r"^相似点\s*\d+$"),
    re.compile(r"^不同点[A-Z]\d+$"),
    re.compile(r"^如同$"),
    re.compile(r"^事物[A-Z]\d+$"),
    re.compile(r"^项目[\d.]+$"),
    re.compile(r"^根主题$"),
    re.compile(r"^类别\s*\d+$"),
    re.compile(r"^分类\s*\d+$"),
    re.compile(r"^叶子\s*\d+$"),
    re.compile(r"^部分\s*\d+$"),
    re.compile(r"^子部分\s*[\d.]+$"),
    re.compile(r"^新子部分\s*[\d.]+$"),  # 新子部分 1, 新子部分 2 (Brace Map default)
    re.compile(r"^左\s*\d+$"),
    re.compile(r"^右\s*\d+$"),
    re.compile(r"^中心主题$"),
    re.compile(r"^主要主题$"),
    re.compile(r"^要点\s*\d+$"),
    re.compile(r"^概念\s*\d+$"),
    re.compile(r"^关联$"),
    re.compile(r"^整体$"),
    re.compile(r"^特征\s*\d+$"),
    re.compile(r"^请输入"),
    re.compile(r"^点击编辑"),
    re.compile(r"^\[点击设置\]$"),  # Bridge map dimension placeholder
]

# English placeholder patterns
_ENGLISH_PLACEHOLDERS = [
    re.compile(r"^Branch\s+\d+$", re.IGNORECASE),
    re.compile(r"^Child\s+[\d.]+$", re.IGNORECASE),
    re.compile(r"^New\s+.*$", re.IGNORECASE),
    re.compile(r"^Attribute\s+\d+$", re.IGNORECASE),
    re.compile(r"^Step\s+\d+$", re.IGNORECASE),
    re.compile(r"^Substep\s+[\d.]+$", re.IGNORECASE),
    re.compile(r"^Cause\s+\d+$", re.IGNORECASE),
    re.compile(r"^Effect\s+\d+$", re.IGNORECASE),
    re.compile(r"^Context\s+\d+$", re.IGNORECASE),
    re.compile(r"^Process$", re.IGNORECASE),
    re.compile(r"^Main\s+Event$", re.IGNORECASE),
    re.compile(r"^Topic\s*\d*$", re.IGNORECASE),
    re.compile(r"^Topic\s+[A-Z]$", re.IGNORECASE),
    re.compile(r"^Similarity\s+\d+$", re.IGNORECASE),
    re.compile(r"^Difference\s+[A-Z]\d+$", re.IGNORECASE),
    re.compile(r"^as$", re.IGNORECASE),
    re.compile(r"^Item\s+\d+$", re.IGNORECASE),
    re.compile(r"^Item\s+[A-Z]$", re.IGNORECASE),
    re.compile(r"^Item\s+[\d.]+$", re.IGNORECASE),
    re.compile(r"^Root\s+Topic$", re.IGNORECASE),
    re.compile(r"^Category\s+\d+$", re.IGNORECASE),
    re.compile(r"^Leaf\s+\d+$", re.IGNORECASE),
    re.compile(r"^Part\s+\d+$", re.IGNORECASE),
    re.compile(r"^Subpart\s+\d+$", re.IGNORECASE),
    re.compile(r"^New\s+Subpart\s+\d+$", re.IGNORECASE),  # New Subpart 1, 2 (Brace Map default)
    re.compile(r"^Left\s+\d+$", re.IGNORECASE),
    re.compile(r"^Right\s+\d+$", re.IGNORECASE),
    re.compile(r"^Main\s+Topic$", re.IGNORECASE),
    re.compile(r"^Central\s+Topic$", re.IGNORECASE),
    re.compile(r"^Point\s+\d+$", re.IGNORECASE),
    re.compile(r"^Concept\s+\d+$", re.IGNORECASE),
    re.compile(r"^Relation(ship)?$", re.IGNORECASE),
    re.compile(r"^Whole$", re.IGNORECASE),
    re.compile(r"^Event$", re.IGNORECASE),
    re.compile(r"^Enter\s+", re.IGNORECASE),
    re.compile(r"^Click\s+to\s+edit", re.IGNORECASE),
    re.compile(r"^Association\s*\d*$", re.IGNORECASE),
    re.compile(r"^Property\s+\d+$", re.IGNORECASE),
]

_PLACEHOLDER_PATTERNS = _CHINESE_PLACEHOLDERS + _ENGLISH_PLACEHOLDERS


def is_placeholder_text(text: Optional[str]) -> bool:
    """
    Check if text is a placeholder that should not be used as real content.

    Aligned with frontend useAutoComplete.ts isPlaceholderText().
    """
    if not text or not isinstance(text, str):
        return True
    stripped = text.strip()
    if not stripped:
        return True
    return any(p.match(stripped) for p in _PLACEHOLDER_PATTERNS)


def filter_for_prompt(
    text: Optional[str],
    fallback_zh: str = "该部分",
    fallback_en: str = "the selected part",
    language: str = "zh",
) -> str:
    """
    Return text for prompt use; use fallback when text is empty or placeholder.

    Used to avoid sending placeholder text like "部分1" to LLM prompts.
    """
    fallback = fallback_zh if language == "zh" else fallback_en
    if not text or not isinstance(text, str):
        return fallback
    stripped = text.strip()
    if not stripped:
        return fallback
    if is_placeholder_text(stripped):
        return fallback
    return stripped
