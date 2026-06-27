"""DingTalk-only display adapter for generate_dingtalk assistant markdown."""

from __future__ import annotations

from services.diagram.assistant_markdown import (
    GENERATED_PREVIEW_MD_RE,
    answer_contains_diagram_preview,
    should_buffer_diagram_markdown_reply,
    strip_diagram_id_html_comments,
)

# Re-export for MindBot pipeline imports.
should_skip_ai_card_for_dingtalk_diagram = should_buffer_diagram_markdown_reply
dingtalk_answer_contains_diagram_preview = answer_contains_diagram_preview


def rewrite_dingtalk_diagram_markdown_alt(text: str) -> str:
    """Use empty alt text — DingTalk markdown mishandles ``![mg:uuid](url)``."""
    return GENERATED_PREVIEW_MD_RE.sub(r"![](\1)", (text or ""))


def format_dingtalk_outbound_markdown(text: str) -> str:
    """
    Format assistant markdown for DingTalk clients only.

    Rewrites ``![mg:uuid](url)`` to ``![](url)`` and hides HTML diagram-id comments.
    The original ``text`` is kept intact for Dify history, usage logs, and MindMate.
    """
    cleaned = rewrite_dingtalk_diagram_markdown_alt(text)
    cleaned = strip_diagram_id_html_comments(cleaned)
    lines = [line.rstrip() for line in cleaned.splitlines()]
    compact = "\n".join(line for line in lines if line.strip())
    return compact.strip() or " "
