"""Voice Notes interchange metadata on stored markdown."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

_VOICE_NOTES_META_BLOCK = re.compile(r"(?:\n|^)<!--\s*mg-voice-notes:1\s*\n[\s\S]*?\n-->\s*$")
_VOICE_NOTES_META_MARKER = "mg-voice-notes:1"


def strip_voice_notes_markdown_meta(markdown: str) -> str:
    """Keep speaker-prefixed transcript lines; drop the trailing meta comment."""
    text = markdown.replace("\r\n", "\n").strip()
    return _VOICE_NOTES_META_BLOCK.sub("", text).strip()


def wrap_voice_notes_markdown(
    transcript: str,
    *,
    saved_at_ms: Optional[int] = None,
    elapsed_ms: int = 0,
) -> str:
    """Attach the same trailing meta block mobile Voice Notes writes to COS."""
    body = strip_voice_notes_markdown_meta(transcript)
    if not body:
        return ""
    if saved_at_ms is None:
        stamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    else:
        stamp = max(0, saved_at_ms)
    meta = {
        "v": 1,
        "ids": [],
        "names": {},
        "slots": [],
        "remaps": {},
        "ctx": "",
        "saved_at": stamp,
        "elapsed_ms": max(0, elapsed_ms),
    }
    encoded = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    return f"{body}\n\n<!-- {_VOICE_NOTES_META_MARKER}\n{encoded}\n-->"
