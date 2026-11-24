"""Build the Word file archived from one MindMate seminar reply."""

from __future__ import annotations

import logging

from services.diagram.assistant_markdown import strip_diagram_id_html_comments
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm import llm_service
from services.mindmate.reply_markdown_docx import (
    GENERIC_DOCX_STEMS,
    build_markdown_docx,
    sanitize_docx_stem,
    summarize_reply_docx_stem,
)
from services.mindmate.teaching_design_docx import build_teaching_design_docx
from services.mindmate.teaching_design_flag import (
    is_teaching_instruction_text,
    strip_reply_kind_markers,
)
from services.mindmate.teaching_design_llm import complete_teaching_design_spec
from services.mindmate.teaching_design_parse import parse_teaching_design_markdown
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import DATABASE_ERRORS, LLM_PIPELINE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_MAX_MARKDOWN_CHARS = 200_000
_ORG_LOOKUP_ERRORS = (*REDIS_ERRORS, *DATABASE_ERRORS)
_TITLE_LLM_ERRORS = (*LLM_PIPELINE_ERRORS, LLMServiceError)
_PLAIN_FALLBACK = "研讨文档"
_TEACHING_FALLBACK = "教学设计"
_TITLE_SYSTEM = "你给教研文档起一个不超过18个汉字的短标题。只输出标题，不要引号、不要扩展名、不要解释。"
_TITLE_USER = "根据下面的正文写一个短标题：\n\n{markdown}"


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
        preferred = (spec.title or "").strip() or (user_prompt or "").strip()
        stem = await resolve_reply_docx_stem(
            cleaned,
            fallback=_TEACHING_FALLBACK,
            preferred=preferred,
            user_id=user_id,
            organization_id=organization_id,
        )
        return payload, f"{stem}.docx"
    cleaned = strip_diagram_id_html_comments(source).strip()
    payload = build_markdown_docx(cleaned)
    stem = await resolve_reply_docx_stem(
        cleaned,
        fallback=_PLAIN_FALLBACK,
        user_id=user_id,
        organization_id=organization_id,
    )
    return payload, f"{stem}.docx"


def _stem_is_specific(stem: str, fallback: str) -> bool:
    cleaned = (stem or "").strip()
    if not cleaned or cleaned == fallback or cleaned in GENERIC_DOCX_STEMS:
        return False
    return len(cleaned) >= 2


async def resolve_reply_docx_stem(
    markdown: str,
    *,
    fallback: str,
    preferred: str = "",
    user_id: int | None,
    organization_id: int | None,
) -> str:
    """Prefer a parsed lesson title; otherwise summarize a short filename stem."""
    if preferred.strip():
        from_preferred = summarize_reply_docx_stem(preferred, fallback)
        if _stem_is_specific(from_preferred, fallback):
            return from_preferred
    heuristic = summarize_reply_docx_stem(markdown, fallback)
    if _stem_is_specific(heuristic, fallback):
        return heuristic
    llm_title = await _llm_short_title(
        markdown,
        user_id=user_id,
        organization_id=organization_id,
    )
    if llm_title:
        return llm_title
    return heuristic or fallback


async def _llm_short_title(
    markdown: str,
    *,
    user_id: int | None,
    organization_id: int | None,
) -> str | None:
    """Ask the model for a short filename when headings are generic section labels."""
    try:
        raw = await llm_service.chat(
            prompt=_TITLE_USER.format(markdown=(markdown or "")[:4000]),
            system_message=_TITLE_SYSTEM,
            model="qwen",
            temperature=0.2,
            max_tokens=40,
            user_id=user_id,
            organization_id=organization_id,
            request_type="reply_docx_title",
            endpoint_path="/api/mindmate/seminar/reply-artifacts",
            use_knowledge_base=False,
        )
    except _TITLE_LLM_ERRORS:
        logger.warning("[ReplyDocx] short_title_llm_failed", exc_info=True)
        return None
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    line = str(raw).strip().splitlines()[0].strip().strip("\"'“”")
    stem = sanitize_docx_stem(line, "")
    if _stem_is_specific(stem, ""):
        return stem[:40]
    return None
