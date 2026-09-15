"""Export a MindMate teaching-design reply as the official BNU Word template."""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from models.domain.auth import User
from services.mindmate.teaching_design_docx import build_teaching_design_docx
from services.mindmate.teaching_design_flag import (
    strip_reply_kind_markers,
    teaching_instruction_from_request,
)
from services.mindmate.teaching_design_llm import complete_teaching_design_spec
from services.mindmate.teaching_design_models import TeachingDesignSpec
from services.mindmate.teaching_design_parse import parse_teaching_design_markdown
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import DATABASE_ERRORS, FILE_IO_ERRORS, REDIS_ERRORS
from utils.auth import get_current_user

_ORG_LOOKUP_ERRORS = (*REDIS_ERRORS, *DATABASE_ERRORS)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

_SAFE_NAME = re.compile(r"[^\w\-.\u4e00-\u9fff]+", re.UNICODE)
_MAX_MARKDOWN_CHARS = 200_000


class TeachingDesignExportBody(BaseModel):
    """JSON body for teaching-design Word export."""

    assistant_markdown: str = Field(..., min_length=1)
    reply_kind: str | None = None
    user_prompt: str | None = None


def _sanitize_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("-", name.strip())[:80].strip("-.")
    return cleaned or "teaching-design"


def _content_disposition(filename: str) -> str:
    """HTTP headers are latin-1; use RFC 5987 for non-ASCII titles."""
    ascii_raw = filename.encode("ascii", "ignore").decode("ascii")
    if ascii_raw.lower().endswith(".docx"):
        ascii_raw = ascii_raw[:-5]
    ascii_stem = _SAFE_NAME.sub("-", ascii_raw).strip("._- ")
    if ascii_stem.lower() in {"doc", "docx"}:
        ascii_stem = ""
    ascii_stem = ascii_stem or "teaching-design"
    ascii_name = f"{ascii_stem}.docx"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _teacher_name(user: User) -> str | None:
    name = getattr(user, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _user_id(user: User) -> int | None:
    raw_id = getattr(user, "id", None)
    if raw_id is None:
        return None
    return int(raw_id)


async def _org_template_key(organization_id: int | None) -> str | None:
    """Pinned school template key, or None to follow the system current file."""
    if organization_id is None:
        return None
    try:
        org = await org_cache.get_by_id(int(organization_id))
    except _ORG_LOOKUP_ERRORS:
        logger.warning(
            "[TeachingDesignExport] org_template_lookup_failed org=%s",
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


def _log_spec(stage: str, user_id: int | None, spec: TeachingDesignSpec) -> None:
    logger.info(
        "[TeachingDesignExport] %s user=%s title=%s prose=%s thinking=%s activities=%s needs_llm=%s leftover=%s",
        stage,
        user_id,
        (spec.title or "")[:60],
        spec.filled_prose_count(),
        len(spec.thinking_points),
        len(spec.activities),
        spec.needs_llm_fill(),
        bool(spec.leftover.strip()),
    )


@router.post("/export_teaching_design_docx")
async def export_teaching_design_docx(
    body: TeachingDesignExportBody,
    user: User = Depends(get_current_user),
) -> Response:
    """Fill the BNU teaching-design template from a flagged MindMate reply."""
    started = time.monotonic()
    user_id = _user_id(user)
    organization_id = getattr(user, "organization_id", None)
    markdown = body.assistant_markdown.strip()
    logger.info(
        "[TeachingDesignExport] start user=%s org=%s markdown_chars=%s reply_kind=%s",
        user_id,
        organization_id,
        len(markdown),
        body.reply_kind,
    )
    if len(markdown) > _MAX_MARKDOWN_CHARS:
        logger.warning(
            "[TeachingDesignExport] rejected_too_large user=%s chars=%s",
            user_id,
            len(markdown),
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="teaching_design_too_large",
        )
    if not teaching_instruction_from_request(body.reply_kind, markdown):
        logger.warning(
            "[TeachingDesignExport] rejected_not_flagged user=%s reply_kind=%s",
            user_id,
            body.reply_kind,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="teaching_design_not_flagged",
        )
    cleaned = strip_reply_kind_markers(markdown)
    parsed = parse_teaching_design_markdown(cleaned)
    _log_spec("parsed", user_id, parsed)
    spec = await complete_teaching_design_spec(
        parsed,
        cleaned,
        user_id=user_id,
        organization_id=organization_id,
        teacher_name=_teacher_name(user),
    )
    _log_spec("mapped", user_id, spec)
    template_key = await _org_template_key(organization_id)
    logger.info(
        "[TeachingDesignExport] template user=%s org=%s key=%s",
        user_id,
        organization_id,
        template_key or "system",
    )
    try:
        docx_bytes = build_teaching_design_docx(spec, template_key=template_key)
    except FileNotFoundError as exc:
        logger.exception(
            "[TeachingDesignExport] template_missing user=%s",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_missing",
        ) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception(
            "[TeachingDesignExport] build_failed user=%s",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_build_failed",
        ) from exc
    fallback_title = (body.user_prompt or "").strip() or "教学设计"
    filename = f"{_sanitize_filename(spec.title or fallback_title)}.docx"
    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "[TeachingDesignExport] done user=%s filename=%s bytes=%s elapsed_ms=%s",
        user_id,
        filename,
        len(docx_bytes),
        elapsed_ms,
    )
    return Response(
        content=docx_bytes,
        media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        headers={"Content-Disposition": _content_disposition(filename)},
    )
