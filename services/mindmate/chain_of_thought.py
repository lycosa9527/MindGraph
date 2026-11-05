"""Apply the organization "show chain-of-thought" switch to MindMate replies.

The admin organization editor stores one switch that sets every chat-scope flag.
Web MindMate and seminar replies follow that switch: hidden thinking is removed
from the stream, and Dify ``agent_thought`` text is included only when the switch is on.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

from services.mindbot.core.reply_thinking import (
    MindbotThinkingStreamFilter,
    extract_dify_agent_thought_text,
)


def organization_shows_chain_of_thought(org: object | None) -> bool:
    """True when the organization editor's chain-of-thought switch is on."""
    if org is None:
        return False
    return bool(
        getattr(org, "show_chain_of_thought_oto", False)
        or getattr(org, "show_chain_of_thought_internal_group", False)
        or getattr(org, "show_chain_of_thought_cross_org_group", False)
    )


class MindmateThinkingGate:
    """Filter one Dify reply so thinking follows the organization switch."""

    def __init__(self, show: bool) -> None:
        """Remember whether this reply should include thinking."""
        self.show = bool(show)
        self._filter = MindbotThinkingStreamFilter(show_chain_of_thought=self.show)
        self._native_parts: list[str] = []

    def on_message_replace(self) -> None:
        """Drop buffered thinking when Dify replaces the in-progress answer."""
        self._filter.reset()
        self._native_parts.clear()

    def visible_answer(self, delta: str) -> str:
        """Return the next user-visible slice of an answer delta."""
        return self._filter.push(delta)

    def note_agent_thought(self, event: dict[str, Any]) -> None:
        """Remember native Dify reasoning. It is shown only when the switch is on."""
        if not self.show:
            return
        text = extract_dify_agent_thought_text(event)
        if text:
            self._native_parts.append(text)

    def closing_thinking_delta(self) -> str:
        """
        Thinking to append once the answer is finished.

        Tag-embedded reasoning already in the answer takes precedence. Native
        ``agent_thought`` text is wrapped only when that answer has none.
        """
        if not self.show:
            return ""
        if self._filter.tag_embedded_reasoning_text.strip():
            return ""
        native = "\n\n".join(self._native_parts).strip()
        if not native:
            return ""
        return f"<think>\n{native}\n</think>\n"
