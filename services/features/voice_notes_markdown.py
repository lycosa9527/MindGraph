"""Strip Voice Notes interchange metadata from stored markdown."""

from __future__ import annotations

import re

_VOICE_NOTES_META_BLOCK = re.compile(r"(?:\n|^)<!--\s*mg-voice-notes:1\s*\n[\s\S]*?\n-->\s*$")


def strip_voice_notes_markdown_meta(markdown: str) -> str:
    """Keep speaker-prefixed transcript lines; drop the trailing meta comment."""
    text = markdown.replace("\r\n", "\n").strip()
    return _VOICE_NOTES_META_BLOCK.sub("", text).strip()
