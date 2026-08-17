"""Generate and persist a Showcase teaching-design cover thumbnail."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from models.domain.showcase import ShowcasePost
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.covers.events import publish_showcase_cover_event
from services.showcase.covers.job_manifest import (
    STAGE_CONVERT,
    STAGE_DOWNLOAD,
    STAGE_UPLOAD,
    bind_cover_job_succeeded,
    mark_cover_job_failed,
    mark_cover_job_running,
    mark_cover_job_stage,
)
from services.showcase.covers.locks import acquire_cover_lock, release_cover_lock
from services.showcase.covers.render import (
    render_pdf_first_page_png,
    resolve_cover_pdf_path,
    shrink_png_bytes,
)
from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage import (
    LOGICAL_PREFIX,
    build_object_key,
    download_to_path_sync,
    put_bytes_sync,
    showcase_public_asset_url,
    storage_backend,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

logger = logging.getLogger(__name__)

_COVER_SUFFIXES = frozenset({".pdf", ".doc", ".docx", ".pptx"})
# Persist LO PDF for inline pdf.js preview (images/shapes/layout). Native PDF
# uses the attachment itself — no separate preview object.
_PREVIEW_PDF_SUFFIXES = frozenset({".doc", ".docx", ".pptx"})


def attachment_key_in_post_scope(post_id: str, attachment_key: str) -> bool:
    """True when key is under showcase/posts/{post_id}/."""
    prefix = f"{LOGICAL_PREFIX}/{post_id}/"
    return bool(attachment_key) and attachment_key.startswith(prefix)


def _spec_attachment_path(spec: Any) -> Optional[str]:
    if not isinstance(spec, dict):
        return None
    value = spec.get("attachment_path")
    return value if isinstance(value, str) and value else None


async def _emit_fail(
    *,
    post_id: str,
    user_id: int,
    attachment_key: str,
    reason: str,
    organization_id: Optional[int] = None,
    author_id: Optional[int] = None,
    celery_task_id: Optional[str] = None,
) -> bool:
    """Log cover_fail, persist manifesto failure, notify SSE, return False."""
    showcase_wf_log(
        "cover_fail",
        reason[:200],
        post_id=post_id,
        user_id=user_id,
        key=attachment_key,
    )
    rls_user_id = int(author_id) if author_id is not None else int(user_id)
    wrote = True
    try:
        # System RLS: cover-job WRITE EXISTS must not depend on author post SELECT.
        async with rls_async_session(RlsContext.system_bootstrap()) as db:
            written = await mark_cover_job_failed(
                db,
                post_id=post_id,
                reason=reason,
                celery_task_id=celery_task_id,
            )
            wrote = written is not None
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[ShowcaseCover] manifesto fail write post=%s user=%s org=%s: %s",
            post_id[:8],
            rls_user_id,
            organization_id,
            exc,
        )
    if wrote:
        await publish_showcase_cover_event(post_id, "cover_fail", reason=reason)
    return False


async def generate_showcase_cover(
    *,
    post_id: str,
    user_id: int,
    attachment_key: str,
    organization_id: Optional[int] = None,
    author_id: Optional[int] = None,
    celery_task_id: Optional[str] = None,
) -> bool:
    """Download attachment, render cover PNG, upload, bind ``thumbnail_path``.

    Soft-fails (returns False) on lock contention, missing post, stale key,
    or render/storage errors. Publishes cover_ready / cover_fail for SSE
    subscribers (except lock_busy — another job owns the cover).
    """
    rls_user_id = int(author_id) if author_id is not None else int(user_id)

    if not attachment_key_in_post_scope(post_id, attachment_key):
        return await _emit_fail(
            post_id=post_id,
            user_id=user_id,
            attachment_key=attachment_key,
            reason="key_out_of_scope",
            organization_id=organization_id,
            author_id=rls_user_id,
            celery_task_id=celery_task_id,
        )

    suffix = Path(attachment_key).suffix.lower()
    if suffix not in _COVER_SUFFIXES:
        return await _emit_fail(
            post_id=post_id,
            user_id=user_id,
            attachment_key=attachment_key,
            reason=f"unsupported_suffix={suffix}",
            organization_id=organization_id,
            author_id=rls_user_id,
            celery_task_id=celery_task_id,
        )

    lock_token = acquire_cover_lock(post_id)
    if lock_token is None:
        showcase_wf_log(
            "cover_skip",
            "lock_busy",
            post_id=post_id,
            user_id=user_id,
            key=attachment_key,
        )
        # Another job is generating; wait for that job's cover_ready/fail.
        return False

    work_dir: Optional[Path] = None
    try:
        showcase_wf_log(
            "cover_start",
            f"suffix={suffix}",
            post_id=post_id,
            user_id=user_id,
            key=attachment_key,
            backend=storage_backend(),
        )

        async with rls_async_session(RlsContext.system_bootstrap()) as db:
            running = await mark_cover_job_running(
                db,
                post_id=post_id,
                attachment_key=attachment_key,
                celery_task_id=celery_task_id,
                stage=STAGE_DOWNLOAD,
            )
            if running is None:
                showcase_wf_log(
                    "cover_skip",
                    "lease_lost",
                    post_id=post_id,
                    user_id=user_id,
                    key=attachment_key,
                )
                return False
            result = await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="post_missing",
                    organization_id=organization_id,
                    author_id=rls_user_id,
                    celery_task_id=celery_task_id,
                )
            if post.case_type != "teaching_design":
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="not_teaching_design",
                    organization_id=organization_id,
                    author_id=rls_user_id,
                    celery_task_id=celery_task_id,
                )
            current_key = _spec_attachment_path(post.spec)
            if current_key != attachment_key:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="stale_attachment_key",
                    organization_id=organization_id,
                    author_id=rls_user_id,
                    celery_task_id=celery_task_id,
                )
            # Keep author id for fail telemetry / enqueue kwargs compatibility.
            rls_user_id = int(post.author_id)

        work_dir = Path(tempfile.mkdtemp(prefix="showcase-cover-"))
        source_path = work_dir / f"source{suffix}"
        if not download_to_path_sync(attachment_key, source_path):
            return await _emit_fail(
                post_id=post_id,
                user_id=user_id,
                attachment_key=attachment_key,
                reason="download_failed",
                organization_id=organization_id,
                author_id=rls_user_id,
                celery_task_id=celery_task_id,
            )

        async with rls_async_session(RlsContext.system_bootstrap()) as db:
            await mark_cover_job_stage(db, post_id=post_id, stage=STAGE_CONVERT)

        pdf_path = resolve_cover_pdf_path(source_path, work_dir / "lo")
        png_bytes = shrink_png_bytes(render_pdf_first_page_png(pdf_path))
        thumb_key = build_object_key(post_id, "thumbnail", ".png")

        async with rls_async_session(RlsContext.system_bootstrap()) as db:
            await mark_cover_job_stage(db, post_id=post_id, stage=STAGE_UPLOAD)

        put_bytes_sync(thumb_key, png_bytes, content_type="image/png")

        preview_key: Optional[str] = None
        if suffix in _PREVIEW_PDF_SUFFIXES:
            preview_key = build_object_key(post_id, "preview", ".pdf")
            put_bytes_sync(
                preview_key,
                pdf_path.read_bytes(),
                content_type="application/pdf",
            )

        async with rls_async_session(RlsContext.system_bootstrap()) as db:
            result = await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="post_gone_before_write",
                    organization_id=organization_id,
                    author_id=rls_user_id,
                    celery_task_id=celery_task_id,
                )
            if _spec_attachment_path(post.spec) != attachment_key:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="stale_attachment_before_write",
                    organization_id=organization_id,
                    author_id=rls_user_id,
                    celery_task_id=celery_task_id,
                )
            post.thumbnail_path = thumb_key
            if preview_key is not None:
                # JSONB: reassignment alone can miss persistence (gallery/upload paths
                # always flag_modified). Without preview_path stuck, detail opens
                # re-enqueue forever.
                spec_obj = dict(post.spec) if isinstance(post.spec, dict) else {}
                spec_obj["preview_path"] = preview_key
                post.spec = spec_obj
                flag_modified(post, "spec")
            # COS (or local) put already done; commit paths + cold succeeded together.
            bound = await bind_cover_job_succeeded(
                db,
                post_id=post_id,
                celery_task_id=celery_task_id,
            )
            if bound is None:
                await db.rollback()
                showcase_wf_log(
                    "cover_skip",
                    "lease_lost",
                    post_id=post_id,
                    user_id=user_id,
                    key=attachment_key,
                )
                return False
            await db.commit()

        await showcase_cache.invalidate_post(post_id)
        thumb_url = showcase_public_asset_url(thumb_key)
        preview_url = showcase_public_asset_url(preview_key) if preview_key is not None else None
        showcase_wf_log(
            "cover_ok",
            f"bytes={len(png_bytes)}",
            post_id=post_id,
            user_id=user_id,
            key=thumb_key,
            backend=storage_backend(),
        )
        await publish_showcase_cover_event(
            post_id,
            "cover_ready",
            thumbnail_url=thumb_url,
            preview_url=preview_url,
        )
        return True
    except (*BACKGROUND_INFRA_ERRORS, *DATABASE_ERRORS, ValueError, OSError) as exc:
        logger.warning(
            "[ShowcaseCover] generate failed post=%s: %s",
            post_id[:8],
            exc,
            exc_info=True,
        )
        return await _emit_fail(
            post_id=post_id,
            user_id=user_id,
            attachment_key=attachment_key,
            reason=str(exc)[:200],
            organization_id=organization_id,
            author_id=rls_user_id,
            celery_task_id=celery_task_id,
        )
    finally:
        release_cover_lock(post_id, lock_token)
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
