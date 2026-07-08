"""Case Square router — moderated public teaching case gallery."""

from __future__ import annotations

import logging
import uuid as uuid_module
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional, Set

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.auth import User
from models.domain.case_square import CaseSquarePost, CaseSquarePostFavorite, CaseSquarePostLike
from utils.db.rls_context import RlsContext, apply_rls_context_async, rls_async_session
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.case_square_constants import (
    CASE_STATUSES,
    CASE_TYPES,
    DIAGRAM_TYPE_LABELS,
    GRADES,
    PUBLISH_SOURCES,
    SORT_OPTIONS,
)
from routers.features.community_helpers import parse_spec_json
from routers.features.case_square_helpers import (
    ALLOWED_DOC_SUFFIXES,
    ALLOWED_SOURCE_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    ATTACHMENT_MAX_BYTES,
    VIDEO_MAX_BYTES,
    apply_gallery_image_uploads,
    assert_gallery_uploads_resolved,
    collect_gallery_images_from_request,
    count_pending_gallery_images,
    resolve_gallery_image_uploads,
    delete_case_file,
    delete_spec_json,
    delete_thumbnail,
    parse_tags_json,
    prepare_post_id_and_spec,
    resolve_gallery_image_storage_path,
    save_case_file,
    save_spec_json,
    save_thumbnail_from_upload,
    validate_gallery_spec,
)
from routers.features.case_square_permissions import (
    can_delete_case,
    can_delist_case,
    can_edit_case,
    can_expert_recommend,
    can_publish_case,
    can_resubmit_case,
    can_review_case,
    can_user_review_post,
    can_view_case_staff_meta,
    can_view_non_approved_post,
    can_withdraw_case,
)
from services.case_square.audit import write_case_square_audit
from services.case_square.field_options import load_meta_payload, validate_grade, validate_subject
from services.case_square.post_delete import case_square_post_still_exists, delete_case_square_post_rows
from services.auth.thinking_coin.case_earn import try_publish_case_earn
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)


async def _safe_case_square_audit(db: AsyncSession, **kwargs) -> None:
    """Write audit log when table/RLS allows; never block delete/review."""
    try:
        await write_case_square_audit(db, **kwargs)
    except DATABASE_ERRORS as exc:
        logger.warning("Case square audit skipped: %s", exc)


router = APIRouter(prefix="/api/case-square", tags=["CaseSquare"])


def _form_flag_true(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


class CaseReviewBody(BaseModel):
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


async def _load_post_for_format(db: AsyncSession, post_id: str) -> CaseSquarePost:
    stmt = (
        select(CaseSquarePost)
        .options(
            joinedload(CaseSquarePost.author).joinedload(User.organization),
            joinedload(CaseSquarePost.reviewer),
            joinedload(CaseSquarePost.expert_recommender),
        )
        .where(CaseSquarePost.id == post_id)
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
    await _safe_case_square_audit(
        db,
        actor_id=actor.id,
        action="delete",
        post_id=post_id,
        payload={"title": title},
    )
    removed = await delete_case_square_post_rows(db, post_id)
    if removed != 1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case",
        )
    await db.commit()
    if await case_square_post_still_exists(db, post_id):
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
        logger.error("[CaseSquare] Panel delete failed for %s: %s", post_id, exc)
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
    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
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

    now = datetime.now(UTC)
    was_pending = post.status == "pending"

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
    if action == "approve" and was_pending:
        try:
            credited, _ = await try_publish_case_earn(db, post.author_id, post.id)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[CaseSquare] Thinking coin credit failed for %s: %s", post_id, exc)

    await _safe_case_square_audit(
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
        logger.error("[CaseSquare] Review commit failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to review case",
        ) from exc

    refreshed = (
        await db.execute(select(CaseSquarePost.status).where(CaseSquarePost.id == post_id))
    ).scalar_one_or_none()
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
                select(CaseSquarePost.views_count).where(
                    CaseSquarePost.id == post_id,
                    CaseSquarePost.status == "approved",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        new_count = int(row) + 1
        await bump_db.execute(update(CaseSquarePost).where(CaseSquarePost.id == post_id).values(views_count=new_count))
        await bump_db.commit()
        return new_count


async def _read_approved_post_likes_count(post_id: str) -> int | None:
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(
                select(CaseSquarePost.likes_count).where(
                    CaseSquarePost.id == post_id,
                    CaseSquarePost.status == "approved",
                )
            )
        ).scalar_one_or_none()
        return None if row is None else int(row)


async def _adjust_approved_post_likes_count(post_id: str, delta: int) -> int | None:
    """Adjust likes_count under system bootstrap — RLS post UPDATE is author/panel-only."""
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(
                select(CaseSquarePost.likes_count).where(
                    CaseSquarePost.id == post_id,
                    CaseSquarePost.status == "approved",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        new_count = max(0, int(row) + delta)
        await bump_db.execute(update(CaseSquarePost).where(CaseSquarePost.id == post_id).values(likes_count=new_count))
        await bump_db.commit()
        return new_count


def _author_payload(post: CaseSquarePost) -> dict:
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
                        "url": f"/static/{path.lstrip('/')}",
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
    post: CaseSquarePost,
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
                select(CaseSquarePostLike).where(
                    CaseSquarePostLike.post_id == post.id,
                    CaseSquarePostLike.user_id == user_id,
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
                select(CaseSquarePostFavorite).where(
                    CaseSquarePostFavorite.post_id == post.id,
                    CaseSquarePostFavorite.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        is_favorited = fav_row is not None

    thumbnail_url = f"/static/{post.thumbnail_path}" if post.thumbnail_path else None
    spec_json_url = f"/static/case_square/{post.id}.json" if post.spec else None

    attachment_url = None
    classroom_video_url = None
    reflection_video_url = None
    source_file_url = None
    if post.spec and isinstance(post.spec, dict):
        attach_path = post.spec.get("attachment_path")
        if isinstance(attach_path, str) and attach_path.strip():
            attachment_url = f"/static/{attach_path.lstrip('/')}"
        classroom_path = post.spec.get("classroom_video_path")
        if isinstance(classroom_path, str) and classroom_path.strip():
            classroom_video_url = f"/static/{classroom_path.lstrip('/')}"
        reflection_path = post.spec.get("reflection_video_path")
        if isinstance(reflection_path, str) and reflection_path.strip():
            reflection_video_url = f"/static/{reflection_path.lstrip('/')}"
        source_path = post.spec.get("source_file_path")
        if isinstance(source_path, str) and source_path.strip():
            source_file_url = f"/static/{source_path.lstrip('/')}"

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
        CaseSquarePost.title.ilike(pattern),
        CaseSquarePost.description.ilike(pattern),
    )


@router.get("/meta")
async def get_meta(
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Filter enums for the Case Square UI."""
    meta = await load_meta_payload(db)
    return {
        **meta,
        "diagram_types": sorted(DIAGRAM_TYPE_LABELS - {"mindmap"}),
        "case_types": sorted(CASE_TYPES),
    }


@router.get("/posts")
async def list_posts(
    case_type: Optional[str] = Query(None),
    expert_recommended: bool = Query(False),
    subject: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    diagram_type: Optional[str] = Query(None),
    publish_source: Optional[str] = Query(None),
    sort: str = Query("default"),
    search: Optional[str] = Query(None, max_length=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    mine: bool = Query(False),
    favorited: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List case square posts. Public feed shows approved only."""
    _validate_sort(sort)
    if case_type:
        _validate_case_type(case_type)
    _validate_optional_filter_text(subject, "subject", max_len=50)
    _validate_optional_filter_text(grade, "grade", max_len=50)
    _validate_optional_diagram_type(diagram_type)
    _validate_optional_publish_source(publish_source)
    if status_filter and status_filter not in CASE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")

    filters = []
    favorite_join = False
    if favorited:
        favorite_join = True
        filters.append(CaseSquarePost.status == "approved")
    elif mine:
        filters.append(CaseSquarePost.author_id == current_user.id)
    elif status_filter and await can_review_case(db, current_user):
        filters.append(CaseSquarePost.status == status_filter)
    else:
        filters.append(CaseSquarePost.status == "approved")

    if case_type:
        filters.append(CaseSquarePost.case_type == case_type)
    if expert_recommended:
        filters.append(CaseSquarePost.is_expert_recommended.is_(True))
    if subject:
        filters.append(CaseSquarePost.subject == subject)
    if grade:
        filters.append(CaseSquarePost.grade == grade)
    if diagram_type:
        filters.append(CaseSquarePost.diagram_type == diagram_type)
    if publish_source:
        filters.append(CaseSquarePost.publish_source == publish_source)
    if search and search.strip():
        filters.append(_search_filter(search))

    count_stmt = select(sa_count()).select_from(CaseSquarePost)
    if favorite_join:
        count_stmt = count_stmt.join(
            CaseSquarePostFavorite,
            (CaseSquarePostFavorite.post_id == CaseSquarePost.id) & (CaseSquarePostFavorite.user_id == current_user.id),
        )
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(CaseSquarePost).options(
        joinedload(CaseSquarePost.author).joinedload(User.organization),
        joinedload(CaseSquarePost.reviewer),
        joinedload(CaseSquarePost.expert_recommender),
    )
    if favorite_join:
        stmt = stmt.join(
            CaseSquarePostFavorite,
            (CaseSquarePostFavorite.post_id == CaseSquarePost.id) & (CaseSquarePostFavorite.user_id == current_user.id),
        )
    if filters:
        stmt = stmt.where(*filters)

    if favorited:
        stmt = stmt.order_by(CaseSquarePostFavorite.created_at.desc())
    elif sort == "hot":
        stmt = stmt.order_by(
            CaseSquarePost.is_expert_recommended.desc(),
            (CaseSquarePost.likes_count + CaseSquarePost.views_count).desc(),
            CaseSquarePost.created_at.desc(),
        )
    elif sort == "newest":
        stmt = stmt.order_by(CaseSquarePost.created_at.desc())
    elif sort == "oldest":
        stmt = stmt.order_by(CaseSquarePost.created_at.asc())
    elif sort == "title_asc":
        stmt = stmt.order_by(CaseSquarePost.title.asc(), CaseSquarePost.created_at.desc())
    elif sort == "title_desc":
        stmt = stmt.order_by(CaseSquarePost.title.desc(), CaseSquarePost.created_at.desc())
    elif sort == "subject_asc":
        stmt = stmt.order_by(
            CaseSquarePost.subject.asc().nulls_last(),
            CaseSquarePost.created_at.desc(),
        )
    elif sort == "subject_desc":
        stmt = stmt.order_by(
            CaseSquarePost.subject.desc().nulls_last(),
            CaseSquarePost.created_at.desc(),
        )
    elif sort == "grade_asc":
        stmt = stmt.order_by(
            CaseSquarePost.grade.asc().nulls_last(),
            CaseSquarePost.created_at.desc(),
        )
    elif sort == "grade_desc":
        stmt = stmt.order_by(
            CaseSquarePost.grade.desc().nulls_last(),
            CaseSquarePost.created_at.desc(),
        )
    elif sort == "reviewed_newest":
        stmt = stmt.order_by(
            CaseSquarePost.reviewed_at.desc().nulls_last(),
            CaseSquarePost.created_at.desc(),
        )
    elif sort == "reviewed_oldest":
        stmt = stmt.order_by(
            CaseSquarePost.reviewed_at.asc().nulls_last(),
            CaseSquarePost.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(
            CaseSquarePost.is_expert_recommended.desc(),
            CaseSquarePost.created_at.desc(),
        )

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    posts = (await db.execute(stmt)).unique().scalars().all()

    liked_post_ids: Set[str] = set()
    if posts:
        post_ids = [p.id for p in posts]
        liked_rows = (
            await db.execute(
                select(CaseSquarePostLike.post_id).where(
                    CaseSquarePostLike.user_id == current_user.id,
                    CaseSquarePostLike.post_id.in_(post_ids),
                )
            )
        ).all()
        liked_post_ids = {row[0] for row in liked_rows}
        favorited_rows = (
            await db.execute(
                select(CaseSquarePostFavorite.post_id).where(
                    CaseSquarePostFavorite.user_id == current_user.id,
                    CaseSquarePostFavorite.post_id.in_(post_ids),
                )
            )
        ).all()
        favorited_post_ids = {row[0] for row in favorited_rows}
    else:
        favorited_post_ids = set()

    formatted = [await _format_post(p, current_user, db, liked_post_ids, favorited_post_ids) for p in posts]
    return {
        "posts": formatted,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
    }


@router.get("/favorites")
async def list_favorite_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List approved posts favorited by the current user."""
    return await list_posts(
        case_type=None,
        expert_recommended=False,
        subject=None,
        grade=None,
        diagram_type=None,
        publish_source=None,
        sort="newest",
        search=None,
        status_filter=None,
        mine=False,
        favorited=True,
        page=page,
        page_size=page_size,
        current_user=current_user,
        db=db,
    )


@router.post("/posts")
async def create_post(
    request: Request,
    title: str = Form(..., min_length=1, max_length=200),
    description: str = Form("", max_length=5000),
    tags: str = Form("[]"),
    case_type: str = Form(...),
    subject: Optional[str] = Form(None),
    grade: Optional[str] = Form(None),
    diagram_type: Optional[str] = Form(None),
    spec: Optional[str] = Form(None),
    teaching_reflection: str = Form(""),
    design_highlights: str = Form(""),
    classroom_application: str = Form(""),
    thumbnail: Optional[UploadFile] = File(None),
    attachment: Optional[UploadFile] = File(None),
    source_file: Optional[UploadFile] = File(None),
    gallery_images: list[UploadFile] = File(default=[]),
    reflection_video: Optional[UploadFile] = File(None),
    classroom_video: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Submit a case for moderation."""
    logger.info("[CaseSquare] create_post user=%s case_type=%s", current_user.id, case_type)
    if not await can_publish_case(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot publish cases")

    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("case_square_create", identifier, max_requests=20, window_seconds=60)

    _validate_case_type(case_type)
    if not subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="subject is required")
    if not grade:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="grade is required")
    try:
        await validate_subject(db, subject)
        await validate_grade(db, grade)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _validate_optional_diagram_type(diagram_type)
    tag_list = parse_tags_json(tags)

    post_id = str(uuid_module.uuid4())
    thumbnail_path = None
    spec_obj: Optional[dict] = None

    if case_type == "teaching_design":
        diagram_type = None
        if not attachment or not attachment.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment is required for teaching design",
            )
        attachment_path = await save_case_file(
            post_id,
            attachment,
            ALLOWED_DOC_SUFFIXES,
            "doc",
            ATTACHMENT_MAX_BYTES,
        )
        spec_obj = {
            "type": "teaching_design",
            "attachment_path": attachment_path,
            "attachment_filename": Path(attachment.filename).name,
        }
        if description.strip():
            spec_obj["body"] = description.strip()
        if teaching_reflection.strip():
            spec_obj["teaching_reflection"] = teaching_reflection.strip()
        if design_highlights.strip():
            spec_obj["design_highlights"] = design_highlights.strip()
        if reflection_video and reflection_video.filename:
            spec_obj["reflection_video_path"] = await save_case_file(
                post_id,
                reflection_video,
                ALLOWED_VIDEO_SUFFIXES,
                "reflection",
                VIDEO_MAX_BYTES,
            )
        if classroom_video and classroom_video.filename:
            spec_obj["classroom_video_path"] = await save_case_file(
                post_id,
                classroom_video,
                ALLOWED_VIDEO_SUFFIXES,
                "classroom",
                VIDEO_MAX_BYTES,
            )
        if thumbnail and thumbnail.filename:
            try:
                thumbnail_path = await save_thumbnail_from_upload(post_id, thumbnail)
            except OSError as err:
                logger.warning("[CaseSquare] Failed to save teaching thumbnail for %s: %s", post_id, err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save thumbnail",
                ) from err
    else:
        if not spec:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="spec is required for diagram cases")
        if not diagram_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="diagram_type is required")
        post_id, spec_obj = prepare_post_id_and_spec(spec)
        validate_gallery_spec(spec_obj)
        if classroom_application.strip():
            spec_obj["classroom_application"] = classroom_application.strip()
        if isinstance(spec_obj.get("gallery"), list):
            pending_images = count_pending_gallery_images(spec_obj)
            resolved_gallery = await resolve_gallery_image_uploads(gallery_images, request)
            if resolved_gallery:
                logger.info(
                    "[CaseSquare] create_post gallery_images=%s pending=%s post=%s",
                    len(resolved_gallery),
                    pending_images,
                    post_id,
                )
                await apply_gallery_image_uploads(post_id, spec_obj, resolved_gallery)
                assert_gallery_uploads_resolved(spec_obj)
            elif pending_images:
                logger.warning(
                    "[CaseSquare] create_post gallery pending=%s but no gallery_images received post=%s",
                    pending_images,
                    post_id,
                )
                spec_obj["source"] = "gallery"
            else:
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
                logger.warning("[CaseSquare] Failed to save thumbnail for %s: %s", post_id, err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save thumbnail",
                ) from err

    if spec_obj:
        save_spec_json(post_id, spec_obj)

    post = CaseSquarePost(
        id=post_id,
        title=title.strip(),
        description=description.strip() or None,
        tags=tag_list,
        case_type=case_type,
        subject=subject,
        grade=grade,
        diagram_type=diagram_type,
        spec=spec_obj,
        thumbnail_path=thumbnail_path,
        author_id=current_user.id,
        submitted_by_id=current_user.id,
        publish_source="self",
        status="pending",
    )
    db.add(post)
    try:
        await db.commit()
        await db.refresh(post)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        delete_thumbnail(post_id)
        delete_spec_json(post_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create case",
        ) from exc

    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Case submitted for review",
        "post": await _format_post(post, current_user, db),
    }


async def _apply_author_case_update(
    post: CaseSquarePost,
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
        if not spec_obj.get("attachment_path") and (not attachment or not attachment.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment is required for teaching design",
            )
        if attachment and attachment.filename:
            attachment_path = await save_case_file(
                post_id,
                attachment,
                ALLOWED_DOC_SUFFIXES,
                "doc",
                ATTACHMENT_MAX_BYTES,
            )
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
                logger.warning("[CaseSquare] Failed to save teaching thumbnail for %s: %s", post_id, err)
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
                    "[CaseSquare] update_post gallery_images=%s post=%s",
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
                logger.warning("[CaseSquare] Failed to save thumbnail for %s: %s", post_id, err)
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


@router.put("/posts/{post_id}")
async def update_post(
    post_id: str,
    request: Request,
    title: str = Form(..., min_length=1, max_length=200),
    description: str = Form("", max_length=5000),
    tags: str = Form("[]"),
    case_type: str = Form(...),
    subject: Optional[str] = Form(None),
    grade: Optional[str] = Form(None),
    diagram_type: Optional[str] = Form(None),
    spec: Optional[str] = Form(None),
    teaching_reflection: str = Form(""),
    design_highlights: str = Form(""),
    classroom_application: str = Form(""),
    thumbnail: Optional[UploadFile] = File(None),
    attachment: Optional[UploadFile] = File(None),
    source_file: Optional[UploadFile] = File(None),
    gallery_images: list[UploadFile] = File(default=[]),
    reflection_video: Optional[UploadFile] = File(None),
    classroom_video: Optional[UploadFile] = File(None),
    remove_reflection_video: str = Form(""),
    remove_classroom_video: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Edit a pending or rejected case; rejected submissions return to the review queue."""
    _validate_post_id(post_id)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("case_square_update", identifier, max_requests=20, window_seconds=60)

    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not await can_edit_case(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit this case")

    try:
        await validate_subject(db, subject or "")
        await validate_grade(db, grade or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    was_rejected = post.status == "rejected"
    is_author = post.author_id == current_user.id
    if not is_author:
        panel_ctx = RlsContext.panel_superadmin(current_user)
        await apply_rls_context_async(db, panel_ctx)

    resolved_gallery = await resolve_gallery_image_uploads(gallery_images, request)
    try:
        await _apply_author_case_update(
            post,
            title=title,
            description=description,
            tags=tags,
            case_type=case_type,
            subject=subject,
            grade=grade,
            diagram_type=diagram_type,
            spec=spec,
            teaching_reflection=teaching_reflection,
            design_highlights=design_highlights,
            classroom_application=classroom_application,
            thumbnail=thumbnail,
            attachment=attachment,
            source_file=source_file,
            gallery_images=resolved_gallery,
            reflection_video=reflection_video,
            classroom_video=classroom_video,
            remove_reflection_video=_form_flag_true(remove_reflection_video),
            remove_classroom_video=_form_flag_true(remove_classroom_video),
        )
        if was_rejected and is_author:
            post.status = "pending"
            post.rejection_reason = None
            post.reviewed_by = None
            post.reviewed_at = None
        await db.commit()
        await db.refresh(post)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update case",
        ) from exc

    post = await _load_post_for_format(db, post_id)
    message = "Case resubmitted for review" if was_rejected and is_author else "Case updated"
    return {
        "message": message,
        "post": await _format_post(post, current_user, db),
    }


@router.post("/posts/{post_id}/gallery-images")
async def upload_post_gallery_images(
    post_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Upload diagram-case gallery images in a dedicated multipart request."""
    _validate_post_id(post_id)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("case_square_update", identifier, max_requests=20, window_seconds=60)

    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not await can_edit_case(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit this case")
    if post.case_type != "diagram_case":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gallery images are only supported for diagram cases",
        )

    gallery_images = await collect_gallery_images_from_request(request)
    if not gallery_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="gallery_images required",
        )

    spec_obj = post.spec if isinstance(post.spec, dict) else None
    if not spec_obj or not isinstance(spec_obj.get("gallery"), list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case has no gallery to attach images to",
        )

    logger.info(
        "[CaseSquare] upload_post_gallery_images post=%s files=%s",
        post_id,
        len(gallery_images),
    )
    await apply_gallery_image_uploads(post_id, spec_obj, gallery_images)
    assert_gallery_uploads_resolved(spec_obj)
    save_spec_json(post_id, spec_obj)
    post.spec = spec_obj
    post.updated_at = datetime.now(UTC)

    try:
        await db.commit()
        await db.refresh(post)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save gallery images",
        ) from exc

    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Gallery images uploaded",
        "post": await _format_post(post, current_user, db),
    }


async def _withdraw_case_post_handler(
    post_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, str]:
    _validate_post_id(post_id)
    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not can_withdraw_case(post, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot withdraw this case")

    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)
    try:
        await _safe_case_square_audit(
            db,
            actor_id=current_user.id,
            action="withdraw",
            post_id=post_id,
            payload={"title": post.title},
        )
        removed = await delete_case_square_post_rows(db, post_id)
        if removed != 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to withdraw case",
            )
        await db.commit()
        if await case_square_post_still_exists(db, post_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to withdraw case",
            )
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[CaseSquare] Withdraw failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to withdraw case",
        ) from exc
    delete_thumbnail(post_id)
    delete_spec_json(post_id)
    return {"message": "Case withdrawn"}


@router.post("/posts/{post_id}/withdraw")
async def withdraw_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Author withdraws a case still under review (hard delete)."""
    return await _withdraw_case_post_handler(post_id, current_user, db)


async def _delist_case_post_handler(
    post_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict:
    _validate_post_id(post_id)
    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not can_delist_case(post, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delist this case")

    now = datetime.now(UTC)
    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)
    try:
        await _safe_case_square_audit(
            db,
            actor_id=current_user.id,
            action="delist",
            post_id=post_id,
            payload={"title": post.title},
        )
        post.status = "withdrawn"
        post.is_expert_recommended = False
        post.expert_recommended_by = None
        post.expert_recommended_at = None
        post.updated_at = now
        await db.commit()
        await db.refresh(post)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[CaseSquare] Delist failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delist case",
        ) from exc

    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Case delisted",
        "post": await _format_post(post, current_user, db),
    }


@router.post("/posts/{post_id}/delist")
async def delist_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Author removes an approved case from the public gallery."""
    return await _delist_case_post_handler(post_id, current_user, db)


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    _validate_post_id(post_id)
    stmt = (
        select(CaseSquarePost)
        .options(
            joinedload(CaseSquarePost.author).joinedload(User.organization),
            joinedload(CaseSquarePost.reviewer),
            joinedload(CaseSquarePost.expert_recommender),
        )
        .where(CaseSquarePost.id == post_id)
    )
    post = (await db.execute(stmt)).unique().scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if post.status != "approved":
        if not await can_view_non_approved_post(post, current_user, db):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if post.status == "approved":
        bumped_views = await _increment_approved_post_views(post_id)
    else:
        bumped_views = None

    # Views are bumped in a system session; suppress autoflush while formatting so a
    # stale ORM instance cannot trigger a user-scoped UPDATE blocked by RLS.
    with db.no_autoflush:
        payload = await _format_post(post, current_user, db)
    if bumped_views is not None:
        payload["views_count"] = bumped_views
    if post.spec:
        payload["spec"] = post.spec
    return payload


async def _delete_case_post_handler(
    post_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, str]:
    _validate_post_id(post_id)
    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not await can_delete_case(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this case")

    await _delete_case_post_with_panel_rls(
        db,
        post_id,
        actor=current_user,
        title=post.title,
    )

    delete_thumbnail(post_id)
    delete_spec_json(post_id)
    return {"message": "Case deleted"}


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    return await _delete_case_post_handler(post_id, current_user, db)


@router.post("/posts/{post_id}/delete")
async def delete_post_via_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """POST alias for environments that block or omit DELETE route registration."""
    return await _delete_case_post_handler(post_id, current_user, db)


@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    _validate_post_id(post_id)
    approved = (
        await db.execute(
            select(CaseSquarePost.id).where(
                CaseSquarePost.id == post_id,
                CaseSquarePost.status == "approved",
            )
        )
    ).scalar_one_or_none()
    if not approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    existing = (
        await db.execute(
            select(CaseSquarePostLike).where(
                CaseSquarePostLike.post_id == post_id,
                CaseSquarePostLike.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    liked = False
    delta = 0
    if existing:
        await db.delete(existing)
        liked = False
        delta = -1
    else:
        db.add(CaseSquarePostLike(post_id=post_id, user_id=current_user.id))
        liked = True
        delta = 1

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        liked = True
        delta = 0

    if delta != 0:
        likes_count = await _adjust_approved_post_likes_count(post_id, delta)
    else:
        likes_count = await _read_approved_post_likes_count(post_id)

    if likes_count is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return {"liked": liked, "likes_count": likes_count}


@router.post("/posts/{post_id}/favorite")
async def toggle_favorite(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    _validate_post_id(post_id)
    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post or post.status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    existing = (
        await db.execute(
            select(CaseSquarePostFavorite).where(
                CaseSquarePostFavorite.post_id == post_id,
                CaseSquarePostFavorite.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        favorited = False
    else:
        db.add(CaseSquarePostFavorite(post_id=post_id, user_id=current_user.id))
        favorited = True

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        favorited = True
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.exception("[CaseSquare] Failed to toggle favorite for post %s", post_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update favorite",
        ) from exc

    return {"favorited": favorited}


@router.post("/posts/{post_id}/recommend")
async def toggle_expert_recommend(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    _validate_post_id(post_id)
    if not await can_expert_recommend(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot recommend cases")

    post = (await db.execute(select(CaseSquarePost).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    if not post or post.status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    now = datetime.now(UTC)
    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)

    if post.is_expert_recommended:
        post.is_expert_recommended = False
        post.expert_recommended_by = None
        post.expert_recommended_at = None
    else:
        post.is_expert_recommended = True
        post.expert_recommended_by = current_user.id
        post.expert_recommended_at = now

    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[CaseSquare] Expert recommend toggle failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update recommendation",
        ) from exc

    with db.no_autoflush:
        refreshed = await _load_post_for_format(db, post_id)
        payload_post = await _format_post(refreshed, current_user, db)
    return {
        "is_expert_recommended": refreshed.is_expert_recommended,
        "post": payload_post,
    }


@router.post("/posts/{post_id}/review")
async def review_post(
    post_id: str,
    body: CaseReviewBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    return await _review_case_post_handler(post_id, body, current_user, db)


@router.get("/pending/count")
async def pending_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    if not await can_review_case(db, current_user):
        return {"count": 0, "pending": 0, "rejected": 0}
    pending = (
        await db.execute(select(sa_count()).select_from(CaseSquarePost).where(CaseSquarePost.status == "pending"))
    ).scalar_one()
    rejected = (
        await db.execute(select(sa_count()).select_from(CaseSquarePost).where(CaseSquarePost.status == "rejected"))
    ).scalar_one()
    return {"count": pending, "pending": pending, "rejected": rejected}
