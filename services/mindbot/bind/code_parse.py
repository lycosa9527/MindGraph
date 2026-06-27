"""Parse rotating DingTalk bind codes from MindBot text messages."""

from __future__ import annotations

import re
from typing import Optional

_BIND_CODE_BODY_RE = re.compile(r"^\s*(\d{3})[\s-]?(\d{3})\s*$")


def format_bind_code_display(code: str) -> str:
    """Format a 6-digit bind code as ``000-000`` for display."""
    digits = (code or "").strip()
    if len(digits) == 6 and digits.isdigit():
        return f"{digits[:3]}-{digits[3:]}"
    return digits


def extract_bind_code_from_text(text: str) -> Optional[str]:
    """
    Return a normalized 6-digit bind code when the message body is only a code.

    Accepts ``123456`` or ``123-456`` (optional whitespace). Returns None for
    normal chat so the MindBot pipeline can continue to Dify.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    match = _BIND_CODE_BODY_RE.fullmatch(raw)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"
