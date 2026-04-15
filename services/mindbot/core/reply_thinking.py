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

# Models may emit whitespace/attributes: < redacted_thinking > ... </ redacted_thinking >
_LOOSE_BLOCK_NAMES: Tuple[str, ...] = ("redacted_thinking", "thinking", "reasoning")

_LOOSE_COMPLETE_RES: Tuple[Pattern[str], ...] = tuple(
    re.compile(
        r"(<\s*"
        + re.escape(name)
        + r"\b[^>]*>)((?:.|\n)*?)(<\s*/\s*"
        + re.escape(name)
        + r"\s*>)",
        re.DOTALL | re.IGNORECASE,
    )
    for name in _LOOSE_BLOCK_NAMES
)


def _strip_loose_complete_blocks(text: str) -> str:
    """Remove thinking-like blocks with flexible whitespace and optional attributes."""
    s = text
    while True:
        prev = s
        for rx in _LOOSE_COMPLETE_RES:
            s = rx.sub("", s)
        if s == prev:
            break
    return s


def _strip_complete_thinking_blocks(text: str) -> str:
    """Remove every complete thinking block (non-overlapping, repeated until stable)."""
    s = text
    while True:
        prev = s
        for rx in _COMPLETE_BLOCK_RES:
            s = rx.sub("", s)
        s = _strip_loose_complete_blocks(s)
        if s == prev:
            break
    return s


def _has_incomplete_thinking_open_prefix(s: str) -> bool:
    """
    True when the buffer ends before ``>`` on a fragment that could still become
    a known thinking open tag (streaming may split ``<redacted_thinking>`` across chunks).
    """
    last_lt = s.rfind("<")
    if last_lt < 0:
        return False
    tail = s[last_lt:]
    if ">" in tail:
        return False
    tail_l = tail.lower()
    for open_tag, _ in _THINK_PAIRS:
        ot = open_tag.lower()
        if len(tail) < len(open_tag) and ot.startswith(tail_l):
            return True
    for name in _LOOSE_BLOCK_NAMES:
        for ws in (0, 1, 2):
            candidate = "<" + (" " * ws) + name + ">"
            if len(tail) < len(candidate) and candidate.lower().startswith(tail_l):
                return True
    return False


def _incomplete_open_cut_index(s: str) -> int:
    """
    Index before any trailing incomplete thinking open tag (streaming-safe).

    If the buffer ends mid-tag, hide from the last ``<`` that starts a known block.
    """
    best = len(s)
    for open_tag, close_tag in _THINK_PAIRS:
        pos = s.rfind(open_tag)
        if pos < 0:
            continue
        tail = s[pos + len(open_tag) :]
        if close_tag not in tail:
            best = min(best, pos)
    last_lt = s.rfind("<")
    if last_lt < 0:
        return best
    tail = s[last_lt:]
    for name in _LOOSE_BLOCK_NAMES:
        open_rx = re.compile(r"<\s*" + re.escape(name) + r"\b[^>]*>", re.IGNORECASE)
        m_open = open_rx.match(tail)
        if not m_open:
            continue
        close_rx = re.compile(
            r"<\s*/\s*" + re.escape(name) + r"\s*>",
            re.IGNORECASE,
        )
        if not close_rx.search(tail):
            best = min(best, last_lt)
            break
    return best


def _hide_thinking_partial_stream(raw: str) -> str:
    """
    Visible prefix of ``raw`` while streaming: drop complete blocks and any
    trailing incomplete opening block.
    """
    s = _strip_complete_thinking_blocks(raw)
    cut = _incomplete_open_cut_index(s)
    return s[:cut]


def _should_hold_stream_until_first_thinking_closes(raw: str) -> bool:
    """
    When chain-of-thought is hidden, return True while any **incomplete** thinking
    block remains in the buffer.

    Complete blocks are stripped first, so after ``</redacted_thinking>`` the next
    incomplete block (if any) still holds streaming until its close arrives.

    Text that arrived before any opening tag is visible in the buffer is emitted
    as it arrives; streaming cannot retract it once sent.
    """
    if not raw:
        return False
    s = _strip_complete_thinking_blocks(raw)
    if _has_incomplete_thinking_open_prefix(s):
        return True
    earliest: tuple[int, int, str, str] | None = None
    for name in _LOOSE_BLOCK_NAMES:
        open_rx = re.compile(r"<\s*" + re.escape(name) + r"\b[^>]*>", re.IGNORECASE)
        m = open_rx.search(s)
        if m:
            if earliest is None:
                earliest = (m.start(), m.end(), "loose", name)
            elif m.start() < earliest[0]:
                earliest = (m.start(), m.end(), "loose", name)
    for open_tag, close_tag in _THINK_PAIRS:
        pos = s.find(open_tag)
        if pos < 0:
            continue
        if earliest is None:
            earliest = (pos, pos + len(open_tag), "exact", close_tag)
        elif pos < earliest[0]:
            earliest = (pos, pos + len(open_tag), "exact", close_tag)
    if earliest is None:
        return False
    _, open_end, kind, key = earliest
    if kind == "loose":
        close_rx = re.compile(r"<\s*/\s*" + re.escape(key) + r"\s*>", re.IGNORECASE)
        return close_rx.search(s[open_end:]) is None
    close_tag = key
    return s.find(close_tag, open_end) < 0


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
    for rx in _LOOSE_COMPLETE_RES:
        s = _truncate_loose_block_match(rx, s, max_chars)
    return s


def _truncate_loose_block_match(rx: Pattern[str], text: str, cap: int) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(2)
        if len(inner) <= cap:
            return m.group(0)
        return m.group(1) + inner[:cap] + "…" + m.group(3)

    return rx.sub(repl, text)


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
    visible characters. After an opening tag appears, while that block is
    incomplete, nothing is emitted until the closing tag arrives (then normal
    strip/partial rules apply). When
    shown, deltas are passed through unchanged (length caps apply to non-streaming
    replies only).
    """

    def __init__(self, *, show_chain_of_thought: bool) -> None:
        self._show = bool(show_chain_of_thought)
        self._raw = ""
        self._sent_visible_len = 0

    def push(self, delta: str) -> str:
        """Append a delta and return the next visible substring (may be empty)."""
        if self._show:
            return delta
        self._raw += delta
        if _should_hold_stream_until_first_thinking_closes(self._raw):
            return ""
        visible = _hide_thinking_partial_stream(self._raw)
        out = visible[self._sent_visible_len :]
        self._sent_visible_len = len(visible)
        return out

    def reset(self) -> None:
        """Clear buffered text and emission cursor."""
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
