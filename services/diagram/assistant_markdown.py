"""Canonical parse helpers for generate_dingtalk assistant markdown.

Dify and ``/api/generate_dingtalk`` store the rich form (``![mg:uuid](url)`` plus
HTML comment). Channel-specific display adapters (MindMate frontend, DingTalk
MindBot) post-process at render/send time without mutating conversation history.
"""

from __future__ import annotations

import re

GENERATED_PREVIEW_MD_RE = re.compile(
    r"!\[[^\]]*\]\((https://[^)\s]+/api/temp_images/dingtalk_[^)\s]+)\)",
    re.IGNORECASE,
)
MG_DIAGRAM_ID_COMMENT_RE = re.compile(
    r"<!--\s*mg-diagram-id:([a-f0-9-]+)\s*-->",
    re.IGNORECASE,
)
MG_DIAGRAM_ID_COMMENT_STRIP_RE = re.compile(
    r"<!--\s*mg-diagram-id:[^>]+-->\s*",
    re.IGNORECASE,
)
MG_LIBRARY_ALT_RE = re.compile(r"!\[mg:([a-f0-9-]+)\]", re.IGNORECASE)
DINGTALK_PREVIEW_UNIQUE_ID_RE = re.compile(
    r"/temp_images/dingtalk_([a-f0-9]{8})_\d+\.png",
    re.IGNORECASE,
)
MG_DID_URL_RE = re.compile(
    r"[?&]mgdid=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def parse_assistant_diagram_library_id(text: str) -> str | None:
    """Return saved library diagram uuid embedded in assistant markdown."""
    raw = (text or "").strip()
    if not raw:
        return None
    comment_match = MG_DIAGRAM_ID_COMMENT_RE.search(raw)
    if comment_match:
        return comment_match.group(1)
    alt_match = MG_LIBRARY_ALT_RE.search(raw)
    if alt_match:
        return alt_match.group(1)
    url_match = MG_DID_URL_RE.search(raw)
    if url_match:
        return url_match.group(1)
    return None


def extract_generate_dingtalk_preview_url(text: str) -> str | None:
    """Return HTTPS temp_images URL from generate_dingtalk markdown."""
    match = GENERATED_PREVIEW_MD_RE.search((text or "").strip())
    if not match:
        return None
    url = match.group(1).strip()
    if not url.lower().startswith("https://"):
        return None
    return url


def extract_preview_unique_id(text: str) -> str | None:
    """Return temp PNG unique id from a generate_dingtalk preview URL in markdown."""
    match = DINGTALK_PREVIEW_UNIQUE_ID_RE.search((text or "").strip())
    if not match:
        return None
    return match.group(1)


def answer_has_library_diagram_uuid(text: str) -> bool:
    """True when markdown includes a saved library uuid marker."""
    return parse_assistant_diagram_library_id(text) is not None


def answer_contains_diagram_preview(text: str) -> bool:
    """True when assistant markdown embeds a generate_dingtalk preview PNG."""
    return extract_generate_dingtalk_preview_url(text) is not None


def strip_diagram_id_html_comments(text: str) -> str:
    """Remove invisible library-id HTML comments from display markdown."""
    return MG_DIAGRAM_ID_COMMENT_STRIP_RE.sub("", text or "")


def should_buffer_diagram_markdown_reply(text: str) -> bool:
    """
    True when the reply is (or is streaming toward) diagram-only preview markdown.

    Callers should buffer SSE silently and send one formatted markdown bubble at end.
    """
    if answer_contains_diagram_preview(text):
        return True
    stripped = (text or "").strip()
    if stripped.startswith("![mg:"):
        return True
    if stripped.startswith("![") and "/api/temp_images/dingtalk_" in stripped.lower():
        without_image = GENERATED_PREVIEW_MD_RE.sub("", stripped)
        without_image = MG_DIAGRAM_ID_COMMENT_STRIP_RE.sub("", without_image).strip()
        if not without_image:
            return True
    return False
