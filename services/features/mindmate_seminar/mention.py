"""
Detect @MindMate mentions in collab chat messages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# @ or fullwidth ＠, not glued to an email local-part.
_MENTION_LEAD = r"(?<![A-Za-z0-9_])"
_MENTION_AT = r"[@＠]"


def _trailing_bound(name: str) -> str:
    """End an @token before CJK when the name itself is ASCII.

    ``@mindmate帮我`` is a mention. ``@mindmatexyz`` and ``@小思你好`` are not:
    a CJK name still needs whitespace or punctuation so it does not eat the
    next word.
    """
    last = name[-1:]
    if last.isascii() and (last.isalnum() or last == "_"):
        return r"(?=$|\s|[^A-Za-z0-9_])"
    return r"(?=$|\s|[^\w])"


def _compile_mention(name: str) -> re.Pattern[str]:
    bound = _trailing_bound(name)
    return re.compile(
        rf"{_MENTION_LEAD}{_MENTION_AT}(?:\*\*)?{re.escape(name)}(?:\*\*)?{bound}",
        re.IGNORECASE,
    )


_MINDMATE_MENTION_RE = _compile_mention("mindmate")


def _alias_pattern(alias: str) -> Optional[re.Pattern[str]]:
    cleaned = alias.strip().lstrip("@＠").strip("*").strip()
    if not cleaned:
        return None
    return _compile_mention(cleaned)


def mention_aliases_from_org(org: object) -> tuple[str, ...]:
    """Saved agent name and alias that should match @-mentions."""
    found: list[str] = []
    for attr in ("mindmate_agent_name", "mindmate_agent_alias"):
        cleaned = str(getattr(org, attr, None) or "").strip()
        if cleaned and cleaned not in found:
            found.append(cleaned)
    return tuple(found)


def collab_message_targets_mindmate(
    explicit_flag: object,
    content: str,
    agent_aliases: Iterable[str] = (),
) -> bool:
    """Route a seminar line to MindMate.

    The MindMate segment sends ``to_mindmate: true`` and always asks the AI.
    The everyone segment sends false, and ``@mindmate`` (or a school alias)
    still asks the AI.
    """
    if explicit_flag is True:
        return True
    return message_mentions_mindmate(content, agent_aliases)


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
