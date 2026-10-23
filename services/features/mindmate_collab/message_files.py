"""Chat-attachment markers stored inside a seminar message body."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\[\[sf:[0-9a-fA-F-]{36}\|[^\]]*\]\]")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def strip_seminar_message_file_tokens(content: str) -> str:
    """Drop attachment markers so MindMate sees the typed text only."""
    cleaned = _TOKEN_RE.sub("", content or "")
    return _BLANK_RUN_RE.sub("\n\n", cleaned).strip()
