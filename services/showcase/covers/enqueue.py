"""Best-effort enqueue of Showcase cover generation (never raises to callers)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from config.celery import celery_app
from services.showcase.covers.config import showcase_server_covers_enabled
from services.showcase.covers.events import (
    clear_cover_last_event_sync,
    publish_showcase_cover_event_sync,
)
from services.showcase.covers.job_manifest import (
    cover_job_blocks_auto_enqueue_sync,
    get_cover_job_snapshot_sync,
    mark_cover_job_failed_sync,
    mark_cover_job_queued_sync,
    snapshot_job_is_in_flight,
)
from services.showcase.covers.locks import try_claim_cover_enqueue
from services.showcase.infra.observability import showcase_wf_log
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS

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
    force: bool = False,
) -> bool:
    """Enqueue Celery cover job when enabled; swallow broker errors.

    Returns True when ``send_task`` was attempted (or deduped while in-flight).
    """
    if not showcase_server_covers_enabled():
        return False
    if case_type != "teaching_design":
        return False
    suffix = Path(attachment_key).suffix.lower()
    if suffix not in _COVER_SUFFIXES:
        return False

    rls_user_id = int(author_id if author_id is not None else user_id)
    if not force and cover_job_blocks_auto_enqueue_sync(
        post_id=post_id,
        attachment_key=attachment_key,
        user_id=rls_user_id,
        organization_id=organization_id,
    ):
        logger.debug(
            "[ShowcaseCover] skip auto-enqueue cold-succeeded post=%s",
            post_id[:8],
        )
        return False

    if force:
        snapshot = get_cover_job_snapshot_sync(
            post_id=post_id,
            user_id=rls_user_id,
            organization_id=organization_id,
        )
        if snapshot_job_is_in_flight(snapshot):
            logger.debug(
                "[ShowcaseCover] force refresh rejected in-flight post=%s",
                post_id[:8],
            )
            return False

    # Admin force must always send_task; dedupe lock is only for auto spam coalesce.
    if not force and not try_claim_cover_enqueue(post_id):
        logger.debug(
            "[ShowcaseCover] enqueue deduped post=%s key=%s",
            post_id[:8],
            attachment_key[:48],
        )
        return True
    # Invalidate prior terminal replay so SSE cannot short-circuit a live job
    # with a stale cover_fail / cover_ready from an earlier attempt.
    clear_cover_last_event_sync(post_id)
    try:
        async_result = celery_app.send_task(
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
        task_id = getattr(async_result, "id", None)
        mark_cover_job_queued_sync(
            post_id=post_id,
            user_id=rls_user_id,
            attachment_key=attachment_key,
            organization_id=organization_id,
            celery_task_id=task_id if isinstance(task_id, str) else None,
            force=force,
        )
        showcase_wf_log(
            "cover_enqueue",
            "ok",
            post_id=post_id,
            user_id=user_id,
            key=attachment_key,
        )
        return True
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
        reason = f"enqueue_failed:{exc}"[:200]
        try:
            mark_cover_job_failed_sync(
                post_id=post_id,
                user_id=rls_user_id,
                reason=reason,
                organization_id=organization_id,
            )
        except DATABASE_ERRORS:
            pass
        publish_showcase_cover_event_sync(
            post_id,
            "cover_fail",
            reason=reason,
        )
        return False


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

    Never auto-requeues a cold-succeeded manifesto (admin Refresh may force).
    Returns True when a job was enqueued (best-effort).
    """
    attachment_key = office_attachment_needs_preview(spec)
    if not attachment_key:
        return False
    rls_user_id = int(author_id)
    if cover_job_blocks_auto_enqueue_sync(
        post_id=post_id,
        attachment_key=attachment_key,
        user_id=rls_user_id,
        organization_id=organization_id,
    ):
        return False
    return enqueue_teaching_design_cover(
        post_id=post_id,
        user_id=int(actor_user_id if actor_user_id is not None else author_id),
        attachment_key=attachment_key,
        case_type=case_type,
        organization_id=organization_id,
        author_id=author_id,
        force=False,
    )
