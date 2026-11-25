"""Chat-attachment markers stored inside a seminar message body."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\[\[sf:([0-9a-fA-F-]{36})\|[^\]]*\]\]")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def extract_seminar_message_file_ids(content: str) -> list[str]:
    """Return unique ``[[sf:uuid|…]]`` ids in the order they appear."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(content or ""):
        file_id = match.group(1)
        if file_id in seen:
            continue
        seen.add(file_id)
        found.append(file_id)
    return found


def strip_seminar_message_file_tokens(content: str) -> str:
    """Drop attachment markers so the typed question is separate from file ids."""
    cleaned = _TOKEN_RE.sub("", content or "")
    return _BLANK_RUN_RE.sub("\n\n", cleaned).strip()
