"""Format Dify / LLM replies for DingTalk: hide or cap chain-of-thought blocks.

When chain-of-thought is hidden, user-visible text is everything *outside* thinking
tags: paired ``<thinking>`` / ``<redacted_thinking>`` / backtick-think blocks are
removed entirely, and while streaming we emit nothing until a block is complete
(including when an open tag is split across SSE chunks).

Native Dify ``agent_thought`` payloads are merged in ``format_mindbot_reply_for_dingtalk``
when enabled; see ``services.mindbot.core.chain_of_thought_policy``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Pattern, Tuple

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


def _normalize_angle_brackets_for_thinking(text: str) -> str:
    """Map fullwidth angle brackets to ASCII so tag patterns match."""
    return text.replace("\uff1c", "<").replace("\uff1e", ">")


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
    s = _normalize_angle_brackets_for_thinking(text)
    while True:
        prev = s
        for rx in _COMPLETE_BLOCK_RES:
            s = rx.sub("", s)
        s = _strip_loose_complete_blocks(s)
        if s == prev:
            break
    return s


def _strip_loose_complete_blocks_capture(s: str, parts: list[str]) -> str:
    """Like ``_strip_loose_complete_blocks`` but append inner text to ``parts``."""
    while True:
        prev = s
        for rx in _LOOSE_COMPLETE_RES:

            def repl(m: re.Match[str]) -> str:
                parts.append(m.group(2))
                return ""

            s = rx.sub(repl, s)
        if s == prev:
            break
    return s


@dataclass(frozen=True)
class SplitReasoningResult:
    """Tag-embedded reasoning vs answer (``answer`` matches ``_strip_complete_thinking_blocks``)."""

    reasoning: str
    answer: str


def split_tag_embedded_reasoning(text: str) -> SplitReasoningResult:
    """
    Split thinking blocks from ``text`` into inner reasoning (joined with newlines)
    and remaining answer string. Extraction order matches ``_strip_complete_thinking_blocks``.
    """
    s = _normalize_angle_brackets_for_thinking(text)
    parts: list[str] = []
    while True:
        prev = s
        for rx in _COMPLETE_BLOCK_RES:

            def repl_exact(m: re.Match[str]) -> str:
                parts.append(m.group(2))
                return ""

            s = rx.sub(repl_exact, s)
        s = _strip_loose_complete_blocks_capture(s, parts)
        if s == prev:
            break
    reasoning = "\n".join(parts) if parts else ""
    return SplitReasoningResult(reasoning=reasoning, answer=s)


def native_reasoning_from_dify_blocking_response(resp: dict[str, Any]) -> str:
    """
    Best-effort reasoning text from a Dify blocking (non-streaming) JSON body.

    Field names are not guaranteed across Dify versions; returns empty when absent.
    """
    for key in ("agent_thought", "thought"):
        val = resp.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    meta = resp.get("metadata")
    if isinstance(meta, dict):
        for key in ("agent_thought", "thought"):
            val = meta.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


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


def _visible_text_hide_chain_of_thought(raw: str) -> str:
    """
    User-visible prefix when CoT is off: never include text inside thinking tags.

    1. Drop every *complete* thinking block (exact, loose, backtick pairs).
    2. If the buffer ends with an incomplete open tag (streaming split) or an open
       block without its closing tag yet, cut before that fragment so we emit nothing
       from inside the block.
    """
    stripped = _strip_complete_thinking_blocks(raw)
    if _has_incomplete_thinking_open_prefix(stripped):
        last_lt = stripped.rfind("<")
        if last_lt >= 0:
            return stripped[:last_lt]
        return ""
    cut = _incomplete_open_cut_index(stripped)
    out = stripped[:cut]
    return out.lstrip("\n\r")


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
    native_reasoning: str = "",
) -> str:
    """
    Final reply string for a completed Dify answer.

    When ``show_chain_of_thought`` is False, thinking blocks are removed entirely.
    When True, inner content of each block is truncated to ``chain_of_thought_max_chars``
    (0 means unlimited).

    ``native_reasoning`` is optional Dify ``agent_thought`` (or blocking) text merged
    only when ``show_chain_of_thought`` is True. If tag-embedded blocks already carry
    reasoning, that content takes precedence and native text is not prepended.
    """
    work = text
    if show_chain_of_thought and native_reasoning.strip():
        nt = native_reasoning.strip()
        sp = split_tag_embedded_reasoning(work)
        tag_r = sp.reasoning.strip()
        if not tag_r:
            work = f"<redacted_thinking>\n{nt}\n</redacted_thinking>\n" + work
    if not show_chain_of_thought:
        return _visible_text_hide_chain_of_thought(work)
    cap = max(0, int(chain_of_thought_max_chars))
    return _truncate_thinking_in_full_text(work, cap)


class MindbotThinkingStreamFilter:
    """
    Incremental filter for streaming Dify answer deltas.

    When chain-of-thought is hidden, each flush recomputes the longest safe prefix
    of the buffer with all thinking blocks removed (nothing is streamed from
    between open/close think tags, including mid-tag SSE splits). When shown,
    deltas pass through unchanged (length caps apply to non-streaming replies only).
    """

    def __init__(self, *, show_chain_of_thought: bool) -> None:
        self._show = bool(show_chain_of_thought)
        self._raw = ""
        self._sent_visible_len = 0
        self._full_for_split = ""

    @property
    def tag_embedded_reasoning_text(self) -> str:
        """Reasoning extracted from tag-embedded blocks in the stream so far."""
        return split_tag_embedded_reasoning(self._full_for_split).reasoning

    def push(self, delta: str) -> str:
        """Append a delta and return the next visible substring (may be empty)."""
        self._full_for_split += delta
        if self._show:
            return delta
        self._raw += delta
        visible = _visible_text_hide_chain_of_thought(self._raw)
        out = visible[self._sent_visible_len :]
        self._sent_visible_len = len(visible)
        return out

    def reset(self) -> None:
        """Clear buffered text and emission cursor."""
        self._raw = ""
        self._sent_visible_len = 0
        self._full_for_split = ""


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
