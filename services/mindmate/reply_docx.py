"""Build the Word file archived from one MindMate seminar reply."""

from __future__ import annotations

import logging

from services.diagram.assistant_markdown import strip_diagram_id_html_comments
from services.mindmate.reply_markdown_docx import build_markdown_docx, reply_docx_filename
from services.mindmate.teaching_design_docx import build_teaching_design_docx
from services.mindmate.teaching_design_flag import (
    is_teaching_instruction_text,
    strip_reply_kind_markers,
)
from services.mindmate.teaching_design_llm import complete_teaching_design_spec
from services.mindmate.teaching_design_parse import parse_teaching_design_markdown
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import DATABASE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_MAX_MARKDOWN_CHARS = 200_000
_ORG_LOOKUP_ERRORS = (*REDIS_ERRORS, *DATABASE_ERRORS)
_PLAIN_FALLBACK = "研讨文档"
_TEACHING_FALLBACK = "教学设计"


async def _org_template_key(organization_id: int | None) -> str | None:
    if organization_id is None:
        return None
    try:
        org = await org_cache.get_by_id(int(organization_id))
    except _ORG_LOOKUP_ERRORS:
        logger.warning(
            "[ReplyDocx] org_template_lookup_failed org=%s",
            organization_id,
            exc_info=True,
        )
        return None
    if org is None:
        return None
    raw = getattr(org, "teaching_design_template_key", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


async def build_archived_reply_docx(
    markdown: str,
    *,
    user_prompt: str | None,
    user_id: int | None,
    organization_id: int | None,
    teacher_name: str | None,
) -> tuple[bytes, str]:
    """Return docx bytes and a filename for a stored assistant reply."""
    source = (markdown or "").strip()
    if not source:
        raise ValueError("empty_reply")
    if len(source) > _MAX_MARKDOWN_CHARS:
        raise ValueError("reply_too_large")
    if is_teaching_instruction_text(source):
        cleaned = strip_reply_kind_markers(source)
        parsed = parse_teaching_design_markdown(cleaned)
        spec = await complete_teaching_design_spec(
            parsed,
            cleaned,
            user_id=user_id,
            organization_id=organization_id,
            teacher_name=teacher_name,
        )
        template_key = await _org_template_key(organization_id)
        payload = build_teaching_design_docx(spec, template_key=template_key)
        title = (spec.title or "").strip() or (user_prompt or "").strip() or _TEACHING_FALLBACK
        return payload, reply_docx_filename(title, _TEACHING_FALLBACK)
    cleaned = strip_diagram_id_html_comments(source).strip()
    payload = build_markdown_docx(cleaned)
    return payload, reply_docx_filename(cleaned, _PLAIN_FALLBACK)
