"""Format Dify / LLM replies for DingTalk: hide or cap chain-of-thought blocks."""

from __future__ import annotations

import re
from typing import Iterable, Pattern, Tuple

# Backtick-delimited `<redacted_thinking>` blocks (common in model outputs).
_BT = chr(96)
_OPEN_BT = _BT + chr(60) + "think" + chr(62) + _BT
_CLOSE_BT = _BT + chr(60) + "/" + "think" + chr(62) + _BT

_THINK_PAIRS: Tuple[Tuple[str, str], ...] = (
    (_OPEN_BT, _CLOSE_BT),
    ("<thinking>", "</thinking>"),
    ("<redacted_thinking>", "</redacted_thinking>"),
)

_COMPLETE_BLOCK_RES: Tuple[Pattern[str], ...] = tuple(
    re.compile(
        "(" + re.escape(open_tag) + r")(.*?)(" + re.escape(close_tag) + r")",
        re.DOTALL | re.IGNORECASE,
    )
    for open_tag, close_tag in _THINK_PAIRS
)


def _strip_complete_thinking_blocks(text: str) -> str:
    """Remove every complete thinking block (non-overlapping, repeated until stable)."""
    s = text
    while True:
        prev = s
        for rx in _COMPLETE_BLOCK_RES:
            s = rx.sub("", s)
        if s == prev:
            break
    return s


def _hide_thinking_partial_stream(raw: str) -> str:
    """
    Visible prefix of ``raw`` while streaming: drop complete blocks and any
    trailing incomplete opening block.
    """
    s = _strip_complete_thinking_blocks(raw)
    best = len(s)
    for open_tag, close_tag in _THINK_PAIRS:
        pos = s.rfind(open_tag)
        if pos < 0:
            continue
        tail = s[pos + len(open_tag) :]
        if close_tag not in tail:
            best = min(best, pos)
    return s[:best]


def _truncate_block_match(rx: Pattern[str], text: str, cap: int) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(2)
        if len(inner) <= cap:
            return m.group(0)
        return m.group(1) + inner[:cap] + "…" + m.group(3)

    return rx.sub(repl, text)


def _truncate_thinking_in_full_text(text: str, max_chars: int) -> str:
    """Keep blocks but cap inner length per block when ``max_chars`` > 0."""
    if max_chars <= 0:
        return text
    s = text
    for rx in _COMPLETE_BLOCK_RES:
        s = _truncate_block_match(rx, s, max_chars)
    return s


def format_mindbot_reply_for_dingtalk(
    text: str,
    *,
    show_chain_of_thought: bool,
    chain_of_thought_max_chars: int,
) -> str:
    """
    Final reply string for a completed Dify answer.

    When ``show_chain_of_thought`` is False, thinking blocks are removed entirely.
    When True, inner content of each block is truncated to ``chain_of_thought_max_chars``
    (0 means unlimited).
    """
    if not show_chain_of_thought:
        return _strip_complete_thinking_blocks(text)
    cap = max(0, int(chain_of_thought_max_chars))
    return _truncate_thinking_in_full_text(text, cap)


class MindbotThinkingStreamFilter:
    """
    Incremental filter for streaming Dify answer deltas.

    When chain-of-thought is hidden, buffers cumulative text and emits only safe
    visible characters. When shown, deltas are passed through unchanged (length
    caps apply to non-streaming replies only).
    """

    def __init__(self, *, show_chain_of_thought: bool) -> None:
        self._show = bool(show_chain_of_thought)
        self._raw = ""
        self._sent_visible_len = 0

    def push(self, delta: str) -> str:
        if self._show:
            return delta
        self._raw += delta
        visible = _hide_thinking_partial_stream(self._raw)
        out = visible[self._sent_visible_len :]
        self._sent_visible_len = len(visible)
        return out

    def reset(self) -> None:
        self._raw = ""
        self._sent_visible_len = 0


def iter_visible_stream_chunks(
    deltas: Iterable[str],
    *,
    show_chain_of_thought: bool,
) -> Iterable[str]:
    """Helper for tests: expand stream deltas to visible chunks."""
    flt = MindbotThinkingStreamFilter(show_chain_of_thought=show_chain_of_thought)
    for d in deltas:
        chunk = flt.push(d)
        if chunk:
            yield chunk
