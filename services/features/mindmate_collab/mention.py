"""
Detect @MindMate mentions in collab chat messages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

_MINDMATE_MENTION_RE = re.compile(r"@mindmate\b", re.IGNORECASE)


def _alias_pattern(alias: str) -> Optional[re.Pattern[str]]:
    cleaned = alias.strip().lstrip("@")
    if not cleaned:
        return None
    return re.compile(rf"@{re.escape(cleaned)}\b", re.IGNORECASE)


def message_mentions_mindmate(content: str, agent_aliases: Iterable[str] = ()) -> bool:
    """Return True when the message @-mentions MindMate or a configured agent alias."""
    text = (content or "").strip()
    if not text:
        return False
    if _MINDMATE_MENTION_RE.search(text):
        return True
    for alias in agent_aliases:
        pattern = _alias_pattern(alias)
        if pattern and pattern.search(text):
            return True
    return False


def extract_mindmate_query(content: str, agent_aliases: Iterable[str] = ()) -> str:
    """Strip @MindMate / agent mentions and return the question for Dify."""
    text = (content or "").strip()
    if not text:
        return text
    text = _MINDMATE_MENTION_RE.sub("", text).strip()
    for alias in agent_aliases:
        pattern = _alias_pattern(alias)
        if pattern:
            text = pattern.sub("", text).strip()
    return text or (content or "").strip()
