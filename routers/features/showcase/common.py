"""Showcase shared helpers used by route modules and admin."""

from __future__ import annotations

from pathlib import Path
import logging
import uuid as uuid_module
from datetime import UTC, datetime
from typing import Optional, Set

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.domain.auth import User
from models.domain.showcase import ShowcasePost, ShowcasePostFavorite, ShowcasePostLike
from routers.features.community.helpers import parse_spec_json
from services.auth.thinking_coin.case_earn import try_publish_case_earn
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.audit import write_showcase_audit
from services.showcase.post_delete import delete_showcase_post_rows, showcase_post_still_exists
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.rls_context import RlsContext, apply_rls_context_async, rls_async_session

from .constants import (
    CASE_TYPES,
    DIAGRAM_TYPE_LABELS,
    GRADES,
    PUBLISH_SOURCES,
    SORT_OPTIONS,
)
from .helpers import (
    ALLOWED_DOC_SUFFIXES,
    ALLOWED_SOURCE_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    ATTACHMENT_MAX_BYTES,
    VIDEO_MAX_BYTES,
    apply_gallery_image_uploads,
    assert_gallery_uploads_resolved,
    assert_post_ready_for_approval,
    count_pending_gallery_images,
    delete_case_file,
    parse_tags_json,
    resolve_gallery_image_storage_path,
    save_case_file,
    save_spec_json,
    save_thumbnail_from_upload,
    showcase_public_asset_url,
    validate_gallery_spec,
)
from .permissions import (
    can_delete_case,
    can_delist_case,
    can_edit_case,
    can_expert_recommend,
    can_resubmit_case,
    can_review_case,
    can_user_review_post,
    can_view_case_staff_meta,
    can_withdraw_case,
)

logger = logging.getLogger(__name__)


async def _safe_showcase_audit(
    db: AsyncSession,
    *,
    actor_id: int,
    action: str,
    post_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Write audit log when table/RLS allows; never block delete/review."""
    try:
        await write_showcase_audit(
            db,
            actor_id=actor_id,
            action=action,
            post_id=post_id,
            payload=payload,
        )
    except DATABASE_ERRORS as exc:
        logger.warning("Case square audit skipped: %s", exc)


def _form_flag_true(value: str) -> bool:
    """Return True when a form flag string is a truthy token."""
    return value.strip().lower() in {"true", "1", "yes"}


class CaseReviewBody(BaseModel):
    """Approve or reject payload for Showcase moderation."""

    action: str = Field(..., description="approve or reject")
    rejection_reason: Optional[str] = Field(None, max_length=500)


def _validate_post_id(post_id: str) -> None:
    try:
        uuid_module.UUID(post_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID format",
        ) from None


def _validate_case_type(value: str) -> None:
    if value not in CASE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid case_type. Allowed: {sorted(CASE_TYPES)}",
        )


def _validate_optional_filter_text(value: Optional[str], field: str, max_len: int = 100) -> None:
    if value is None:
        return
    trimmed = value.strip()
    if not trimmed or len(trimmed) > max_len:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field}")


def _validate_optional_publish_source(value: Optional[str]) -> None:
    if value is not None and value not in PUBLISH_SOURCES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid publish_source")


def _validate_optional_grade(value: Optional[str]) -> None:
    if value is not None and value not in GRADES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid grade")


def _validate_optional_diagram_type(value: Optional[str]) -> None:
    if value is not None and value not in DIAGRAM_TYPE_LABELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid diagram_type")


def _validate_sort(value: str) -> None:
    if value not in SORT_OPTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sort")


async def _load_post_for_format(db: AsyncSession, post_id: str) -> ShowcasePost:
    stmt = (
        select(ShowcasePost)
        .options(
            joinedload(ShowcasePost.author).joinedload(User.organization),
            joinedload(ShowcasePost.reviewer),
            joinedload(ShowcasePost.expert_recommender),
        )
        .where(ShowcasePost.id == post_id)
    )
    return (await db.execute(stmt)).unique().scalar_one()


async def _delete_case_post_in_session(
    db: AsyncSession,
    post_id: str,
    *,
    actor: User,
    title: str,
) -> None:
    """Delete under panel RLS on the open session (must call apply_rls_context_async first)."""
    await _safe_showcase_audit(
        db,
        actor_id=actor.id,
        action="delete",
        post_id=post_id,
        payload={"title": title},
    )
    removed = await delete_showcase_post_rows(db, post_id)
    if removed != 1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case",
        )
    await db.commit()
    if await showcase_post_still_exists(db, post_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case",
        )


async def _delete_case_post_with_panel_rls(
    db: AsyncSession,
    post_id: str,
    *,
    actor: User,
    title: str,
) -> None:
    panel_ctx = RlsContext.panel_superadmin(actor)
    await apply_rls_context_async(db, panel_ctx)
    try:
        await _delete_case_post_in_session(db, post_id, actor=actor, title=title)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Showcase] Panel delete failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case",
        ) from exc


async def _review_case_post_handler(
    post_id: str,
    body: CaseReviewBody,
    current_user: User,
    db: AsyncSession,
    *,
    skip_self_review_guard: bool = False,
) -> dict:
    _validate_post_id(post_id)
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if skip_self_review_guard:
        if not await can_review_case(db, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot review cases")
    elif not await can_user_review_post(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot review cases")

    action = body.action.strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action must be approve or reject")

    if post.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending cases can be reviewed",
        )

    if action == "approve":
        assert_post_ready_for_approval(
            case_type=post.case_type,
            spec=post.spec if isinstance(post.spec, dict) else None,
        )

    now = datetime.now(UTC)

    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)

    if action == "approve":
        post.status = "approved"
        post.rejection_reason = None
    else:
        post.status = "rejected"
        post.rejection_reason = (body.rejection_reason or "").strip() or None
        post.is_expert_recommended = False
        post.expert_recommended_by = None
        post.expert_recommended_at = None

    post.reviewed_by = current_user.id
    post.reviewed_at = now

    credited = 0
    if action == "approve":
        try:
            credited, _ = await try_publish_case_earn(db, post.author_id, post.id)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[Showcase] Thinking coin credit failed for %s: %s", post_id, exc)

    await _safe_showcase_audit(
        db,
        actor_id=current_user.id,
        action="review_approve" if action == "approve" else "review_reject",
        post_id=post_id,
        payload={"rejection_reason": post.rejection_reason},
    )

    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Showcase] Review commit failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to review case",
        ) from exc

    await showcase_cache.invalidate_post(post_id)
    refreshed = (await db.execute(select(ShowcasePost.status).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    expected = "approved" if action == "approve" else "rejected"
    if refreshed != expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to review case",
        )

    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Case approved" if action == "approve" else "Case rejected",
        "credited_coins": credited,
        "post": await _format_post(post, current_user, db),
    }


async def _increment_approved_post_views(post_id: str) -> int | None:
    """Bump views under system bootstrap — RLS post UPDATE is author/panel-only."""
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(
                select(ShowcasePost.views_count).where(
                    ShowcasePost.id == post_id,
                    ShowcasePost.status == "approved",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        new_count = int(row) + 1
        await bump_db.execute(update(ShowcasePost).where(ShowcasePost.id == post_id).values(views_count=new_count))
        await bump_db.commit()
        return new_count


async def _read_approved_post_likes_count(post_id: str) -> int | None:
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(
                select(ShowcasePost.likes_count).where(
                    ShowcasePost.id == post_id,
                    ShowcasePost.status == "approved",
                )
            )
        ).scalar_one_or_none()
        return None if row is None else int(row)


async def _adjust_approved_post_likes_count(post_id: str, delta: int) -> int | None:
    """Adjust likes_count under system bootstrap — RLS post UPDATE is author/panel-only."""
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(
                select(ShowcasePost.likes_count).where(
                    ShowcasePost.id == post_id,
                    ShowcasePost.status == "approved",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        new_count = max(0, int(row) + delta)
        await bump_db.execute(update(ShowcasePost).where(ShowcasePost.id == post_id).values(likes_count=new_count))
        await bump_db.commit()
        return new_count


def _author_payload(post: ShowcasePost) -> dict:
    attr = post.attribution if isinstance(post.attribution, dict) else {}
    if post.publish_source == "proxy" and isinstance(attr.get("display_name"), str) and attr["display_name"].strip():
        org = attr.get("organization")
        org_str = org.strip() if isinstance(org, str) and org.strip() else None
        if org_str is None and post.author.organization:
            org_str = post.author.organization.name
        return {
            "id": post.author_id,
            "name": attr["display_name"].strip(),
            "avatar": post.author.avatar or "👤",
            "organization": org_str,
            "is_proxy": True,
        }
    return {
        "id": post.author_id,
        "name": post.author.name or "Anonymous",
        "avatar": post.author.avatar or "👤",
        "organization": (post.author.organization.name if post.author.organization else None),
        "is_proxy": False,
    }


def _format_gallery_items(spec: dict | None, post_id: str) -> list[dict]:
    if not spec or not isinstance(spec, dict):
        return []
    gallery = spec.get("gallery")
    if not isinstance(gallery, list):
        return []
    items: list[dict] = []
    for slot, entry in enumerate(gallery):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == "image":
            path = resolve_gallery_image_storage_path(post_id, slot, entry)
            if path:
                items.append(
                    {
                        "kind": "image",
                        "url": showcase_public_asset_url(path),
                        "filename": entry.get("filename"),
                    }
                )
            else:
                items.append(
                    {
                        "kind": "image",
                        "url": None,
                        "missing": True,
                        "filename": entry.get("filename"),
                    }
                )
        elif kind == "diagram":
            payload: dict = {
                "kind": "diagram",
                "diagram_id": entry.get("diagram_id"),
                "title": entry.get("title"),
                "diagram_type": entry.get("diagram_type"),
            }
            if isinstance(entry.get("spec"), dict):
                payload["spec"] = entry["spec"]
            items.append(payload)
    return items


async def _format_post(
    post: ShowcasePost,
    current_user: User,
    db: AsyncSession,
    liked_post_ids: Optional[Set[str]] = None,
    favorited_post_ids: Optional[Set[str]] = None,
) -> dict:
    user_id = current_user.id
    is_liked = False
    if liked_post_ids is not None:
        is_liked = post.id in liked_post_ids
    else:
        row = (
            await db.execute(
                select(ShowcasePostLike).where(
                    ShowcasePostLike.post_id == post.id,
                    ShowcasePostLike.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        is_liked = row is not None

    is_favorited = False
    if favorited_post_ids is not None:
        is_favorited = post.id in favorited_post_ids
    else:
        fav_row = (
            await db.execute(
                select(ShowcasePostFavorite).where(
                    ShowcasePostFavorite.post_id == post.id,
                    ShowcasePostFavorite.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        is_favorited = fav_row is not None

    thumbnail_url = showcase_public_asset_url(post.thumbnail_path) if post.thumbnail_path else None
    # Spec is PG-backed; URL hits authenticated assets route which synthesizes JSON
    spec_json_url = showcase_public_asset_url(f"case_square/{post.id}.json") if post.spec else None

    attachment_url = None
    classroom_video_url = None
    reflection_video_url = None
    source_file_url = None
    if post.spec and isinstance(post.spec, dict):
        attach_path = post.spec.get("attachment_path")
        if isinstance(attach_path, str) and attach_path.strip():
            attachment_url = showcase_public_asset_url(attach_path.lstrip("/"))
        classroom_path = post.spec.get("classroom_video_path")
        if isinstance(classroom_path, str) and classroom_path.strip():
            classroom_video_url = showcase_public_asset_url(classroom_path.lstrip("/"))
        reflection_path = post.spec.get("reflection_video_path")
        if isinstance(reflection_path, str) and reflection_path.strip():
            reflection_video_url = showcase_public_asset_url(reflection_path.lstrip("/"))
        source_path = post.spec.get("source_file_path")
        if isinstance(source_path, str) and source_path.strip():
            source_file_url = showcase_public_asset_url(source_path.lstrip("/"))

    gallery_items = _format_gallery_items(post.spec if isinstance(post.spec, dict) else None, post.id)

    reviewer = await can_review_case(db, current_user)
    user_perms_review = await can_user_review_post(post, current_user, db)
    can_del = await can_delete_case(post, current_user, db)
    can_edit = await can_edit_case(post, current_user, db)
    can_rec = await can_expert_recommend(db, current_user)
    can_withdraw = can_withdraw_case(post, current_user)
    can_delist = can_delist_case(post, current_user)
    can_resubmit = can_resubmit_case(post, current_user)
    show_staff_meta = await can_view_case_staff_meta(db, current_user)

    def _staff_user_name(user: User | None) -> str:
        if not user:
            return "—"
        return (user.name if user.name else None) or (user.phone if user.phone else None) or "—"

    reviewer_payload = None
    if show_staff_meta and post.reviewed_by is not None:
        reviewer_payload = {
            "id": post.reviewed_by,
            "name": _staff_user_name(post.reviewer),
        }

    expert_recommender_payload = None
    if show_staff_meta and post.expert_recommended_by is not None:
        expert_recommender_payload = {
            "id": post.expert_recommended_by,
            "name": _staff_user_name(post.expert_recommender),
        }

    return {
        "id": post.id,
        "title": post.title,
        "description": post.description,
        "tags": post.tags or [],
        "case_type": post.case_type,
        "subject": post.subject,
        "grade": post.grade,
        "diagram_type": post.diagram_type,
        "thumbnail_url": thumbnail_url,
        "spec_json_url": spec_json_url,
        "attachment_url": attachment_url,
        "classroom_video_url": classroom_video_url,
        "reflection_video_url": reflection_video_url,
        "source_file_url": source_file_url,
        "gallery_items": gallery_items,
        "status": post.status,
        "is_expert_recommended": post.is_expert_recommended,
        "publish_source": post.publish_source,
        "attribution": post.attribution if post.publish_source == "proxy" else None,
        "rejection_reason": (
            post.rejection_reason if post.author_id == user_id or post.submitted_by_id == user_id or reviewer else None
        ),
        "author": _author_payload(post),
        "likes_count": post.likes_count,
        "views_count": post.views_count,
        "created_at": post.created_at.isoformat() if post.created_at else "",
        "reviewed_at": (post.reviewed_at.isoformat() if show_staff_meta and post.reviewed_at else None),
        "reviewer": reviewer_payload,
        "expert_recommender": expert_recommender_payload,
        "expert_recommended_at": (
            post.expert_recommended_at.isoformat() if show_staff_meta and post.expert_recommended_at else None
        ),
        "is_liked": is_liked,
        "is_favorited": is_favorited,
        "can_edit": can_edit,
        "can_delete": can_del,
        "can_withdraw": can_withdraw,
        "can_delist": can_delist,
        "can_resubmit": can_resubmit,
        "can_review": user_perms_review,
        "can_expert_recommend": can_rec,
    }


def _search_filter(query: str):
    pattern = f"%{query.strip()}%"
    return or_(
        ShowcasePost.title.ilike(pattern),
        ShowcasePost.description.ilike(pattern),
    )


async def _apply_author_case_update(
    post: ShowcasePost,
    *,
    title: str,
    description: str,
    tags: str,
    case_type: str,
    subject: Optional[str],
    grade: Optional[str],
    diagram_type: Optional[str],
    spec: Optional[str],
    teaching_reflection: str,
    design_highlights: str,
    classroom_application: str,
    thumbnail: Optional[UploadFile],
    attachment: Optional[UploadFile],
    source_file: Optional[UploadFile],
    gallery_images: list[UploadFile],
    reflection_video: Optional[UploadFile],
    classroom_video: Optional[UploadFile],
    remove_reflection_video: bool = False,
    remove_classroom_video: bool = False,
) -> None:
    """Mutate post fields/spec for author edit; caller commits."""
    if case_type != post.case_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="case_type cannot be changed when editing",
        )
    _validate_case_type(case_type)
    if not subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="subject is required")
    if not grade:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="grade is required")

    tag_list = parse_tags_json(tags)
    post_id = post.id
    spec_obj: Optional[dict] = dict(post.spec) if isinstance(post.spec, dict) else None
    thumbnail_path = post.thumbnail_path

    if case_type == "teaching_design":
        diagram_type = None
        if not spec_obj:
            spec_obj = {"type": "teaching_design"}
        if attachment and attachment.filename:
            attachment_path = await save_case_file(
                post_id,
                attachment,
                ALLOWED_DOC_SUFFIXES,
                "doc",
                ATTACHMENT_MAX_BYTES,
            )
            old_path = spec_obj.get("attachment_path")
            if isinstance(old_path, str) and old_path and old_path != attachment_path:
                delete_case_file(old_path)
            spec_obj["attachment_path"] = attachment_path
            spec_obj["attachment_filename"] = Path(attachment.filename).name
        if description.strip():
            spec_obj["body"] = description.strip()
        elif "body" in spec_obj:
            del spec_obj["body"]
        if teaching_reflection.strip():
            spec_obj["teaching_reflection"] = teaching_reflection.strip()
        elif "teaching_reflection" in spec_obj:
            del spec_obj["teaching_reflection"]
        if design_highlights.strip():
            spec_obj["design_highlights"] = design_highlights.strip()
        elif "design_highlights" in spec_obj:
            del spec_obj["design_highlights"]
        if reflection_video and reflection_video.filename:
            spec_obj["reflection_video_path"] = await save_case_file(
                post_id,
                reflection_video,
                ALLOWED_VIDEO_SUFFIXES,
                "reflection",
                VIDEO_MAX_BYTES,
            )
        elif remove_reflection_video:
            old_path = spec_obj.get("reflection_video_path")
            if isinstance(old_path, str) and old_path.strip():
                delete_case_file(old_path)
            spec_obj.pop("reflection_video_path", None)
        if classroom_video and classroom_video.filename:
            spec_obj["classroom_video_path"] = await save_case_file(
                post_id,
                classroom_video,
                ALLOWED_VIDEO_SUFFIXES,
                "classroom",
                VIDEO_MAX_BYTES,
            )
        elif remove_classroom_video:
            old_path = spec_obj.get("classroom_video_path")
            if isinstance(old_path, str) and old_path.strip():
                delete_case_file(old_path)
            spec_obj.pop("classroom_video_path", None)
        if thumbnail and thumbnail.filename:
            try:
                thumbnail_path = await save_thumbnail_from_upload(post_id, thumbnail)
            except OSError as err:
                logger.warning("[Showcase] Failed to save teaching thumbnail for %s: %s", post_id, err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save thumbnail",
                ) from err
        elif not thumbnail_path and attachment and attachment.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="thumbnail is required",
            )
    else:
        if not diagram_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="diagram_type is required")
        _validate_optional_diagram_type(diagram_type)
        if spec:
            spec_obj = parse_spec_json(spec)
        if not spec_obj:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="spec is required for diagram cases")
        validate_gallery_spec(spec_obj)
        if classroom_application.strip():
            spec_obj["classroom_application"] = classroom_application.strip()
        elif "classroom_application" in spec_obj:
            del spec_obj["classroom_application"]
        if isinstance(spec_obj.get("gallery"), list):
            if gallery_images:
                logger.info(
                    "[Showcase] update_post gallery_images=%s post=%s",
                    len(gallery_images),
                    post_id,
                )
                await apply_gallery_image_uploads(post_id, spec_obj, gallery_images)
                assert_gallery_uploads_resolved(spec_obj)
            elif count_pending_gallery_images(spec_obj) == 0:
                spec_obj["source"] = "gallery"
        if source_file and source_file.filename:
            spec_obj["source_file_path"] = await save_case_file(
                post_id,
                source_file,
                ALLOWED_SOURCE_SUFFIXES,
                "source",
                ATTACHMENT_MAX_BYTES,
            )
        if thumbnail and thumbnail.filename:
            try:
                thumbnail_path = await save_thumbnail_from_upload(post_id, thumbnail)
            except OSError as err:
                logger.warning("[Showcase] Failed to save thumbnail for %s: %s", post_id, err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save thumbnail",
                ) from err

    if spec_obj:
        save_spec_json(post_id, spec_obj)

    post.title = title.strip()
    post.description = description.strip() or None
    post.tags = tag_list
    post.subject = subject
    post.grade = grade
    post.diagram_type = diagram_type
    post.spec = spec_obj
    post.thumbnail_path = thumbnail_path
    post.updated_at = datetime.now(UTC)
