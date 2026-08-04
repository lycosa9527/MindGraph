"""Best-effort enqueue of Showcase cover generation (never raises to callers)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from config.celery import celery_app
from services.showcase.covers.config import showcase_server_covers_enabled
from services.showcase.covers.events import publish_showcase_cover_event_sync
from services.showcase.covers.locks import try_claim_cover_enqueue
from services.showcase.infra.observability import showcase_wf_log
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_COVER_SUFFIXES = frozenset({".pdf", ".doc", ".docx", ".pptx"})
# Office formats that need LO PDF for the detail reader (pdf.js).
_OFFICE_PREVIEW_SUFFIXES = frozenset({".doc", ".docx", ".pptx"})
_COVER_TASK_NAME = "showcase.generate_cover"


def office_attachment_needs_preview(spec: Any) -> Optional[str]:
    """Return attachment key when teaching Office doc has no ``preview_path``."""
    if not isinstance(spec, dict):
        return None
    attachment = spec.get("attachment_path")
    if not isinstance(attachment, str) or not attachment.strip():
        return None
    suffix = Path(attachment).suffix.lower()
    if suffix not in _OFFICE_PREVIEW_SUFFIXES:
        return None
    preview = spec.get("preview_path")
    if isinstance(preview, str) and preview.strip():
        return None
    return attachment


def enqueue_teaching_design_cover(
    *,
    post_id: str,
    user_id: int,
    attachment_key: str,
    case_type: str,
    organization_id: Optional[int] = None,
    author_id: Optional[int] = None,
) -> None:
    """Enqueue Celery cover job when enabled; swallow broker errors."""
    if not showcase_server_covers_enabled():
        return
    if case_type != "teaching_design":
        return
    suffix = Path(attachment_key).suffix.lower()
    if suffix not in _COVER_SUFFIXES:
        return
    if not try_claim_cover_enqueue(post_id):
        logger.debug(
            "[ShowcaseCover] enqueue deduped post=%s key=%s",
            post_id[:8],
            attachment_key[:48],
        )
        return
    try:
        celery_app.send_task(
            _COVER_TASK_NAME,
            kwargs={
                "post_id": post_id,
                "user_id": user_id,
                "attachment_key": attachment_key,
                "organization_id": organization_id,
                "author_id": author_id if author_id is not None else user_id,
            },
            queue="default",
        )
        showcase_wf_log(
            "cover_enqueue",
            "ok",
            post_id=post_id,
            user_id=user_id,
            key=attachment_key,
        )
    except (*BACKGROUND_INFRA_ERRORS, RuntimeError, ValueError, TypeError) as exc:
        logger.warning(
            "[ShowcaseCover] enqueue failed post=%s: %s",
            post_id[:8],
            exc,
        )
        showcase_wf_log(
            "cover_enqueue_fail",
            str(exc)[:200],
            post_id=post_id,
            user_id=user_id,
            key=attachment_key,
        )
        publish_showcase_cover_event_sync(
            post_id,
            "cover_fail",
            reason=f"enqueue_failed:{exc}"[:200],
        )


def enqueue_missing_office_preview(
    *,
    post_id: str,
    case_type: str,
    spec: Any,
    author_id: int,
    organization_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
) -> bool:
    """Enqueue cover/preview regen when Office attachment lacks ``preview_path``.

    Returns True when a job was enqueued (best-effort; broker errors still True
    only when ``send_task`` was attempted — callers treat as fire-and-forget).
    """
    attachment_key = office_attachment_needs_preview(spec)
    if not attachment_key:
        return False
    enqueue_teaching_design_cover(
        post_id=post_id,
        user_id=int(actor_user_id if actor_user_id is not None else author_id),
        attachment_key=attachment_key,
        case_type=case_type,
        organization_id=organization_id,
        author_id=author_id,
    )
    return True
