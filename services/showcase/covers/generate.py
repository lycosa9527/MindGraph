"""Generate and persist a Showcase teaching-design cover thumbnail."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from models.domain.showcase import ShowcasePost
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.covers.events import publish_showcase_cover_event
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
) -> bool:
    """Log cover_fail, notify SSE subscribers, return False."""
    showcase_wf_log(
        "cover_fail",
        reason[:200],
        post_id=post_id,
        user_id=user_id,
        key=attachment_key,
    )
    await publish_showcase_cover_event(post_id, "cover_fail", reason=reason)
    return False


async def generate_showcase_cover(
    *,
    post_id: str,
    user_id: int,
    attachment_key: str,
    organization_id: Optional[int] = None,
    author_id: Optional[int] = None,
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
        )

    suffix = Path(attachment_key).suffix.lower()
    if suffix not in _COVER_SUFFIXES:
        return await _emit_fail(
            post_id=post_id,
            user_id=user_id,
            attachment_key=attachment_key,
            reason=f"unsupported_suffix={suffix}",
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

        async with rls_async_session(RlsContext.for_celery_user(rls_user_id, organization_id)) as db:
            result = await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="post_missing",
                )
            if post.case_type != "teaching_design":
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="not_teaching_design",
                )
            current_key = _spec_attachment_path(post.spec)
            if current_key != attachment_key:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="stale_attachment_key",
                )
            # Prefer DB author for RLS write even if enqueue omitted author_id.
            rls_user_id = int(post.author_id)

        work_dir = Path(tempfile.mkdtemp(prefix="showcase-cover-"))
        source_path = work_dir / f"source{suffix}"
        if not download_to_path_sync(attachment_key, source_path):
            return await _emit_fail(
                post_id=post_id,
                user_id=user_id,
                attachment_key=attachment_key,
                reason="download_failed",
            )

        pdf_path = resolve_cover_pdf_path(source_path, work_dir / "lo")
        png_bytes = shrink_png_bytes(render_pdf_first_page_png(pdf_path))
        thumb_key = build_object_key(post_id, "thumbnail", ".png")
        put_bytes_sync(thumb_key, png_bytes, content_type="image/png")

        preview_key: Optional[str] = None
        if suffix == ".pptx":
            preview_key = build_object_key(post_id, "preview", ".pdf")
            put_bytes_sync(
                preview_key,
                pdf_path.read_bytes(),
                content_type="application/pdf",
            )

        async with rls_async_session(RlsContext.for_celery_user(rls_user_id, organization_id)) as db:
            result = await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="post_gone_before_write",
                )
            if _spec_attachment_path(post.spec) != attachment_key:
                return await _emit_fail(
                    post_id=post_id,
                    user_id=user_id,
                    attachment_key=attachment_key,
                    reason="stale_attachment_before_write",
                )
            post.thumbnail_path = thumb_key
            if preview_key is not None:
                spec_obj = dict(post.spec) if isinstance(post.spec, dict) else {}
                spec_obj["preview_path"] = preview_key
                post.spec = spec_obj
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
        )
    finally:
        release_cover_lock(post_id, lock_token)
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
