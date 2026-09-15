"""Parse and hide MindMate teaching-instruction reply markers."""

from __future__ import annotations

import re
from typing import Any

REPLY_KIND_TEACHING_INSTRUCTION = "teaching_instruction"

COMMENT_RE = re.compile(
    r"<!--\s*mg-reply-kind:\s*([a-z0-9_-]+)\s*-->",
    re.IGNORECASE,
)
COMMENT_STRIP_RE = re.compile(
    r"<!--\s*mg-reply-kind:[^>]+-->\s*",
    re.IGNORECASE,
)
BRACKET_RE = re.compile(
    r"\[\s*mg-reply-kind:\s*([a-z0-9_-]+)\s*\]",
    re.IGNORECASE,
)
BRACKET_STRIP_RE = re.compile(
    r"\[\s*mg-reply-kind:[^\]]+\]\s*",
    re.IGNORECASE,
)
_TRUTHY_STRINGS = frozenset({"1", "true", "yes", "on", REPLY_KIND_TEACHING_INSTRUCTION})


def strip_reply_kind_markers(text: str) -> str:
    """Remove hidden teaching-instruction markers from display markdown."""
    cleaned = COMMENT_STRIP_RE.sub("", text or "")
    cleaned = BRACKET_STRIP_RE.sub("", cleaned)
    return cleaned.strip()


def _normalized_kind(raw: str | None) -> str | None:
    if not raw:
        return None
    kind = raw.strip().lower().replace("-", "_")
    if kind == REPLY_KIND_TEACHING_INSTRUCTION:
        return REPLY_KIND_TEACHING_INSTRUCTION
    return None


def parse_reply_kind_from_text(text: str) -> str | None:
    """Return teaching_instruction when a durable answer marker is present."""
    comment = COMMENT_RE.search(text or "")
    kind = _normalized_kind(comment.group(1) if comment else None)
    if kind:
        return kind
    bracket = BRACKET_RE.search(text or "")
    return _normalized_kind(bracket.group(1) if bracket else None)


def is_teaching_instruction_text(text: str) -> bool:
    """True when assistant markdown carries the teaching-instruction marker."""
    return parse_reply_kind_from_text(text) == REPLY_KIND_TEACHING_INSTRUCTION


def _is_truthy_flag(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY_STRINGS
    if isinstance(value, (int, float)):
        return value == 1
    return False


def parse_reply_kind_from_outputs(outputs: Any) -> str | None:
    """Read optional workflow_finished.outputs for the same reply kind."""
    if not isinstance(outputs, dict):
        return None
    kind = outputs.get("mg_reply_kind") or outputs.get("reply_kind")
    if isinstance(kind, str):
        normalized = _normalized_kind(kind)
        if normalized:
            return normalized
    if _is_truthy_flag(outputs.get("export_word_template")):
        return REPLY_KIND_TEACHING_INSTRUCTION
    return None


def teaching_instruction_from_request(reply_kind: str | None, markdown: str) -> bool:
    """True when the export API may build the official BNU form."""
    if _normalized_kind(reply_kind) == REPLY_KIND_TEACHING_INSTRUCTION:
        return True
    return is_teaching_instruction_text(markdown)


def mindmate_meta_payload() -> dict[str, Any]:
    """Synthetic SSE body consumed by the MindMate web client."""
    return {
        "event": "mindmate_meta",
        "reply_kind": REPLY_KIND_TEACHING_INSTRUCTION,
        "export_word_template": True,
    }


def mindmate_meta_from_workflow_chunk(chunk: dict[str, Any]) -> dict[str, Any] | None:
    """Build mindmate_meta when workflow_finished outputs flag the instruction branch."""
    if chunk.get("event") != "workflow_finished":
        return None
    data = chunk.get("data")
    outputs = data.get("outputs") if isinstance(data, dict) else None
    if parse_reply_kind_from_outputs(outputs):
        return mindmate_meta_payload()
    return None
