"""Validation and sanitization for school consultation form payloads."""

from __future__ import annotations

import re

PHONE_ALLOWED_CHARS = re.compile(r"^[\d\s+\-()]+$")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
FAKE_MENTION = re.compile(r"<@[^>\s]+>")

NAME_MAX_LEN = 64
PHONE_MAX_LEN = 32
ORG_MAX_LEN = 128
NOTE_MAX_LEN = 500


def _collapse_whitespace(value: str, *, keep_newlines: bool) -> str:
    if keep_newlines:
        lines = [re.sub(r"[ \t]+", " ", line.strip()) for line in value.splitlines()]
        return "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", value.strip())


def sanitize_consult_field(value: str, *, max_len: int, keep_newlines: bool = False) -> str:
    """Normalize user text before WeCom markdown rendering."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("required")
    cleaned = CONTROL_CHARS.sub("", cleaned)
    cleaned = FAKE_MENTION.sub("", cleaned)
    cleaned = _collapse_whitespace(cleaned, keep_newlines=keep_newlines)
    if not cleaned:
        raise ValueError("required")
    if len(cleaned) > max_len:
        raise ValueError("too_long")
    return cleaned


def validate_consult_phone(value: str) -> str:
    """Accept CN-style mobiles and reasonable landline/international numbers."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("required")
    if len(cleaned) > PHONE_MAX_LEN:
        raise ValueError("too_long")
    if not PHONE_ALLOWED_CHARS.match(cleaned):
        raise ValueError("invalid_phone")
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 7 or len(digits) > 15:
        raise ValueError("invalid_phone")
    return cleaned
