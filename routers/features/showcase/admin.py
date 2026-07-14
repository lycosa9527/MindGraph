"""Showcase admin API — stats, grants, fields, proxy publish."""

from __future__ import annotations

import logging
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.domain.auth import User
from models.domain.showcase import ShowcasePost
from models.domain.showcase_admin import ShowcaseFieldOption, ShowcaseStaffGrant
from routers.auth.dependencies import get_async_db_with_request_rls, require_panel_capability
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.audit import write_showcase_audit
from services.showcase.field_options import (
    invalidate_field_options_cache_async,
    validate_grade,
    validate_subject,
)
from services.showcase.posts.lifecycle import rollback_created_post_assets
from services.showcase.staff_permissions import (
    ALL_SHOWCASE_PERMS,
    PLATFORM_BD_DEFAULT,
    can_view_dashboard as can_view_showcase_dashboard,
)
from services.showcase.storage import cos_showcase_enabled, delete_post_assets
from services.showcase.sync import (
    build_storage_status,
    purge_orphans_from_reconcile,
    reconcile_showcase_storage,
)
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.admin_panel_permissions import CAP_TAB_SHOWCASE_EDIT, CAP_TAB_SHOWCASE_VIEW
from utils.auth.admin_scope import AdminScope
from utils.auth.role_constants import ROLE_PLATFORM_BD, SUPERADMIN_ROLES

from .common import (
    CaseReviewBody,
    _delete_case_post_in_session,
    _format_post,
    _load_post_for_format,
    _review_case_post_handler,
)
from .constants import CASE_TYPES, DIAGRAM_TYPE_LABELS
from .helpers import (
    ALLOWED_DOC_SUFFIXES,
    ALLOWED_SOURCE_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    ATTACHMENT_MAX_BYTES,
    VIDEO_MAX_BYTES,
    parse_tags_json,
    post_media_ready_for_approval,
    prepare_post_id_and_spec,
    save_case_file,
    save_spec_json,
    save_thumbnail_from_upload,
)
from .permissions import (
    PERM_DELETE,
    PERM_FIELDS,
    PERM_PERMISSIONS,
    PERM_PUBLISH_PROXY,
    PERM_REVIEW,
    VALID_GRANT_PERMISSIONS,
    can_delete_case,
    can_review_case,
    load_user_showcase_permissions,
)
from .routes_uploads import reject_if_cos_multipart_files_present

logger = logging.getLogger(__name__)

router = APIRouter()


class StaffGrantBody(BaseModel):
    """Request body to create or update a Showcase staff grant."""

    user_id: int
    permissions: list[str] = Field(default_factory=list)
    note: Optional[str] = None
    expires_at: Optional[datetime] = None


class StaffGrantPatchBody(BaseModel):
    """Partial update payload for an existing staff grant."""

    permissions: Optional[list[str]] = None
    note: Optional[str] = None
    expires_at: Optional[datetime] = None


class FieldOptionBody(BaseModel):
    """Request body to create a subject, grade, or recommended-tag option."""

    category: str
    value: str = Field(..., min_length=1, max_length=100)
    label_zh: Optional[str] = None
    label_en: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class FieldOptionPatchBody(BaseModel):
    """Partial update payload for a field option."""

    label_zh: Optional[str] = None
    label_en: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


async def _require_perm(db: AsyncSession, user: User, perm: str) -> frozenset[str]:
    perms = await load_user_showcase_permissions(db, user)
    if perm not in perms:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient Showcase permission")
    return perms


async def _builtin_staff_rows(db: AsyncSession) -> list[dict[str, Any]]:
    """Platform roles with built-in Showcase permissions (not stored in grants table)."""
    rows = (
        (
            await db.execute(
                select(User)
                .options(joinedload(User.organization))
                .where(User.role.in_(list(SUPERADMIN_ROLES | frozenset({ROLE_PLATFORM_BD}))))
                .order_by(User.id.asc())
            )
        )
        .unique()
        .scalars()
        .all()
    )
    builtin: list[dict[str, Any]] = []
    for user in rows:
        if user.role in SUPERADMIN_ROLES:
            perms = sorted(ALL_SHOWCASE_PERMS)
            role_label = "superadmin"
        else:
            perms = sorted(PLATFORM_BD_DEFAULT)
            role_label = ROLE_PLATFORM_BD
        builtin.append(
            {
                "id": None,
                "user_id": user.id,
                "user_name": user.name,
                "user_phone": user.phone,
                "organization": user.organization.name if user.organization else None,
                "permissions": perms,
                "note": "内置角色权限",
                "expires_at": None,
                "granted_by_name": None,
                "source": "builtin",
                "builtin_role": role_label,
                "editable": False,
            }
        )
    return builtin


def _sanitize_grant_permissions(raw: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in raw:
        if isinstance(item, str) and item in VALID_GRANT_PERMISSIONS and item != PERM_PERMISSIONS:
            if item not in cleaned:
                cleaned.append(item)
    return cleaned


@router.get("/admin/showcase/stats/overview")
async def showcase_stats_overview(
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Return Showcase moderation and engagement stats for the admin dashboard."""
    if not await can_view_showcase_dashboard(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient Showcase permission")
    now = datetime.now(UTC)
    since = now - timedelta(days=period_days)

    pending = (
        await db.execute(select(func.count()).select_from(ShowcasePost).where(ShowcasePost.status == "pending"))
    ).scalar_one()
    approved_total = (
        await db.execute(select(func.count()).select_from(ShowcasePost).where(ShowcasePost.status == "approved"))
    ).scalar_one()
    rejected_total = (
        await db.execute(select(func.count()).select_from(ShowcasePost).where(ShowcasePost.status == "rejected"))
    ).scalar_one()
    created_recent = (
        await db.execute(select(func.count()).select_from(ShowcasePost).where(ShowcasePost.created_at >= since))
    ).scalar_one()
    approved_recent = (
        await db.execute(
            select(func.count())
            .select_from(ShowcasePost)
            .where(ShowcasePost.status == "approved", ShowcasePost.reviewed_at >= since)
        )
    ).scalar_one()
    proxy_total = (
        await db.execute(select(func.count()).select_from(ShowcasePost).where(ShowcasePost.publish_source == "proxy"))
    ).scalar_one()
    expert_total = (
        await db.execute(
            select(func.count())
            .select_from(ShowcasePost)
            .where(ShowcasePost.is_expert_recommended.is_(True), ShowcasePost.status == "approved")
        )
    ).scalar_one()

    reviewed_recent = (
        approved_recent
        + (
            await db.execute(
                select(func.count())
                .select_from(ShowcasePost)
                .where(ShowcasePost.status == "rejected", ShowcasePost.reviewed_at >= since)
            )
        ).scalar_one()
    )
    rejection_rate = 0.0
    if reviewed_recent > 0:
        rejected_recent = (
            await db.execute(
                select(func.count())
                .select_from(ShowcasePost)
                .where(ShowcasePost.status == "rejected", ShowcasePost.reviewed_at >= since)
            )
        ).scalar_one()
        rejection_rate = round(rejected_recent / reviewed_recent, 4)

    self_total = (
        await db.execute(select(func.count()).select_from(ShowcasePost).where(ShowcasePost.publish_source == "self"))
    ).scalar_one()
    total_posts = int(pending) + int(approved_total) + int(rejected_total)

    case_type_rows = (
        await db.execute(select(ShowcasePost.case_type, func.count()).group_by(ShowcasePost.case_type))
    ).all()
    by_case_type = {str(row[0]): int(row[1]) for row in case_type_rows}

    views_sum = (await db.execute(select(func.coalesce(func.sum(ShowcasePost.views_count), 0)))).scalar_one()
    likes_sum = (await db.execute(select(func.coalesce(func.sum(ShowcasePost.likes_count), 0)))).scalar_one()

    rejected_recent_count = (
        await db.execute(
            select(func.count())
            .select_from(ShowcasePost)
            .where(ShowcasePost.status == "rejected", ShowcasePost.reviewed_at >= since)
        )
    ).scalar_one()

    return {
        "pending": pending,
        "approved_total": approved_total,
        "rejected_total": rejected_total,
        "total_posts": total_posts,
        "created_recent": created_recent,
        "approved_recent": approved_recent,
        "rejected_recent": rejected_recent_count,
        "proxy_total": proxy_total,
        "self_total": self_total,
        "expert_recommended_total": expert_total,
        "rejection_rate_recent": rejection_rate,
        "by_case_type": by_case_type,
        "total_views": int(views_sum or 0),
        "total_likes": int(likes_sum or 0),
        "period_days": period_days,
    }


@router.get("/admin/showcase/staff-grants")
async def list_staff_grants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """List custom staff grants and built-in role permissions."""
    await _require_perm(db, current_user, PERM_PERMISSIONS)
    rows = (
        (
            await db.execute(
                select(ShowcaseStaffGrant)
                .options(
                    joinedload(ShowcaseStaffGrant.user).joinedload(User.organization),
                    joinedload(ShowcaseStaffGrant.granter),
                )
                .order_by(ShowcaseStaffGrant.updated_at.desc())
            )
        )
        .unique()
        .scalars()
        .all()
    )
    custom_grants = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "user_name": row.user.name if row.user else None,
            "user_phone": row.user.phone if row.user else None,
            "organization": row.user.organization.name if row.user and row.user.organization else None,
            "permissions": row.permissions or [],
            "note": row.note,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "granted_by": row.granted_by,
            "granted_by_name": row.granter.name if row.granter else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "source": "grant",
            "editable": True,
        }
        for row in rows
    ]
    builtin = await _builtin_staff_rows(db)
    return {"grants": custom_grants, "builtin": builtin}


@router.post("/admin/showcase/staff-grants")
async def upsert_staff_grant(
    body: StaffGrantBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Create or update a user's Showcase staff grant."""
    await _require_perm(db, current_user, PERM_PERMISSIONS)
    perms = _sanitize_grant_permissions(body.permissions)
    if not perms:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one permission required")

    target = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    row = (
        await db.execute(select(ShowcaseStaffGrant).where(ShowcaseStaffGrant.user_id == body.user_id))
    ).scalar_one_or_none()
    if row is None:
        row = ShowcaseStaffGrant(user_id=body.user_id)
        db.add(row)
    row.permissions = perms
    row.note = (body.note or "").strip() or None
    row.expires_at = body.expires_at
    row.granted_by = current_user.id
    row.updated_at = datetime.now(UTC)

    await write_showcase_audit(
        db,
        actor_id=current_user.id,
        action="grant_change",
        payload={"user_id": body.user_id, "permissions": perms},
    )
    await db.commit()
    return {"message": "Grant saved", "user_id": body.user_id, "permissions": perms}


@router.delete("/admin/showcase/staff-grants/{user_id}")
async def delete_staff_grant(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Revoke a custom staff grant for a user."""
    await _require_perm(db, current_user, PERM_PERMISSIONS)
    row = (
        await db.execute(select(ShowcaseStaffGrant).where(ShowcaseStaffGrant.user_id == user_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")
    await db.delete(row)
    await write_showcase_audit(
        db,
        actor_id=current_user.id,
        action="grant_revoke",
        payload={"user_id": user_id},
    )
    await db.commit()
    return {"message": "Grant removed"}


@router.get("/admin/showcase/field-options")
async def list_field_options(
    category: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """List Showcase subject, grade, and recommended-tag options."""
    perms = await load_user_showcase_permissions(db, current_user)
    if PERM_FIELDS not in perms and PERM_REVIEW not in perms:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")

    stmt = select(ShowcaseFieldOption).order_by(
        ShowcaseFieldOption.category,
        ShowcaseFieldOption.sort_order,
        ShowcaseFieldOption.value,
    )
    if category:
        stmt = stmt.where(ShowcaseFieldOption.category == category)
    if not include_inactive:
        stmt = stmt.where(ShowcaseFieldOption.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "options": [
            {
                "id": row.id,
                "category": row.category,
                "value": row.value,
                "label_zh": row.label_zh or row.value,
                "label_en": row.label_en,
                "sort_order": row.sort_order,
                "is_active": row.is_active,
            }
            for row in rows
        ]
    }


@router.post("/admin/showcase/field-options")
async def create_field_option(
    body: FieldOptionBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Create a new Showcase field option."""
    await _require_perm(db, current_user, PERM_FIELDS)
    if body.category not in ("subject", "grade", "recommended_tag"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category")
    row = ShowcaseFieldOption(
        category=body.category,
        value=body.value.strip(),
        label_zh=(body.label_zh or body.value).strip(),
        label_en=body.label_en,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(row)
    await write_showcase_audit(
        db,
        actor_id=current_user.id,
        action="field_create",
        payload={"category": body.category, "value": body.value},
    )
    await db.commit()
    await invalidate_field_options_cache_async()
    await db.refresh(row)
    return {"message": "Created", "id": row.id}


@router.patch("/admin/showcase/field-options/{option_id}")
async def patch_field_option(
    option_id: int,
    body: FieldOptionPatchBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Update labels, sort order, or active flag for a field option."""
    await _require_perm(db, current_user, PERM_FIELDS)
    row = (
        await db.execute(select(ShowcaseFieldOption).where(ShowcaseFieldOption.id == option_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")
    if body.label_zh is not None:
        row.label_zh = body.label_zh.strip() or row.value
    if body.label_en is not None:
        row.label_en = body.label_en
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    if body.is_active is not None:
        row.is_active = body.is_active
    row.updated_at = datetime.now(UTC)
    await write_showcase_audit(
        db,
        actor_id=current_user.id,
        action="field_update",
        payload={"id": option_id, "category": row.category, "value": row.value},
    )
    await db.commit()
    await invalidate_field_options_cache_async()
    return {"message": "Updated"}


@router.delete("/admin/showcase/field-options/{option_id}")
async def delete_field_option(
    option_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Remove a Showcase field option."""
    await _require_perm(db, current_user, PERM_FIELDS)
    row = (
        await db.execute(select(ShowcaseFieldOption).where(ShowcaseFieldOption.id == option_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")
    await db.delete(row)
    await write_showcase_audit(
        db,
        actor_id=current_user.id,
        action="field_delete",
        payload={"id": option_id, "category": row.category, "value": row.value},
    )
    await db.commit()
    await invalidate_field_options_cache_async()
    return {"message": "Deleted"}


async def _admin_delete_case_post_handler(
    post_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, str]:
    try:
        uuid_module.UUID(post_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID format",
        ) from exc

    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not await can_delete_case(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this case")

    thumb_path = post.thumbnail_path
    spec_snapshot = dict(post.spec) if isinstance(post.spec, dict) else None
    try:
        await _delete_case_post_in_session(
            db,
            post_id,
            actor=current_user,
            title=post.title,
        )
    except DATABASE_ERRORS as exc:
        logger.error("[Showcase] Admin delete failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case",
        ) from exc

    await delete_post_assets(post_id=post_id, thumbnail_path=thumb_path, spec=spec_snapshot)
    await showcase_cache.invalidate_post(post_id)
    return {"message": "Case deleted"}


@router.delete("/admin/showcase/posts/{post_id}")
async def admin_delete_case_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_EDIT)),
):
    """Delete a case from the admin panel (panel RLS session from get_admin_scope)."""
    return await _admin_delete_case_post_handler(post_id, current_user, db)


@router.post("/admin/showcase/posts/{post_id}/delete")
async def admin_delete_case_post_via_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_EDIT)),
):
    """POST alias — preferred from admin UI (avoids DELETE / 405 on stale deployments)."""
    return await _admin_delete_case_post_handler(post_id, current_user, db)


@router.post("/admin/showcase/posts/{post_id}/review")
async def admin_review_case_post(
    post_id: str,
    body: CaseReviewBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_EDIT)),
):
    """Moderation review from admin panel (panel RLS; allows queue review including own demo rows)."""
    if not await can_review_case(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot review cases")
    return await _review_case_post_handler(
        post_id,
        body,
        current_user,
        db,
        skip_self_review_guard=True,
    )


@router.post("/admin/showcase/posts/proxy")
async def proxy_create_post(
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
    attribution_name: str = Form(..., min_length=1, max_length=100),
    attribution_org: str = Form(""),
    auto_approve: bool = Form(False),
    thumbnail: Optional[UploadFile] = File(None),
    attachment: Optional[UploadFile] = File(None),
    source_file: Optional[UploadFile] = File(None),
    reflection_video: Optional[UploadFile] = File(None),
    classroom_video: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Publish a case on behalf of an external or offline author."""
    perms = await _require_perm(db, current_user, PERM_PUBLISH_PROXY)

    if case_type not in CASE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid case_type")
    if not subject or not grade:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="subject and grade required")
    try:
        await validate_subject(db, subject)
        await validate_grade(db, grade)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    tag_list = parse_tags_json(tags)
    reject_if_cos_multipart_files_present(
        any(
            [
                bool(thumbnail and thumbnail.filename),
                bool(attachment and attachment.filename),
                bool(source_file and source_file.filename),
                bool(reflection_video and reflection_video.filename),
                bool(classroom_video and classroom_video.filename),
            ]
        )
    )
    post_id = str(uuid_module.uuid4())
    thumbnail_path = None
    spec_obj: Optional[dict] = None

    if case_type == "teaching_design":
        diagram_type = None
        spec_obj = {"type": "teaching_design"}
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
        if teaching_reflection.strip():
            spec_obj["teaching_reflection"] = teaching_reflection.strip()
        if design_highlights.strip():
            spec_obj["design_highlights"] = design_highlights.strip()
        if reflection_video and reflection_video.filename:
            spec_obj["reflection_video_path"] = await save_case_file(
                post_id, reflection_video, ALLOWED_VIDEO_SUFFIXES, "reflection", VIDEO_MAX_BYTES
            )
        if classroom_video and classroom_video.filename:
            spec_obj["classroom_video_path"] = await save_case_file(
                post_id, classroom_video, ALLOWED_VIDEO_SUFFIXES, "classroom", VIDEO_MAX_BYTES
            )
        if thumbnail and thumbnail.filename:
            thumbnail_path = await save_thumbnail_from_upload(post_id, thumbnail)
    else:
        if not spec or not diagram_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="spec and diagram_type required")
        if diagram_type not in DIAGRAM_TYPE_LABELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid diagram_type")
        post_id, spec_obj = prepare_post_id_and_spec(spec)
        if classroom_application.strip():
            spec_obj["classroom_application"] = classroom_application.strip()
        if source_file and source_file.filename:
            spec_obj["source_file_path"] = await save_case_file(
                post_id, source_file, ALLOWED_SOURCE_SUFFIXES, "source", ATTACHMENT_MAX_BYTES
            )
        if thumbnail and thumbnail.filename:
            thumbnail_path = await save_thumbnail_from_upload(post_id, thumbnail)
        elif not cos_showcase_enabled():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="thumbnail required")

    if spec_obj:
        save_spec_json(post_id, spec_obj)

    initial_status = "pending"
    if (
        auto_approve
        and PERM_REVIEW in perms
        and post_media_ready_for_approval(case_type=case_type, spec=spec_obj)
    ):
        # Only auto-approve when create-time media is already complete (COS
        # create-then-upload must approve after uploads finish).
        initial_status = "approved"
    attribution = {
        "display_name": attribution_name.strip(),
        "organization": attribution_org.strip() or None,
        "is_external": True,
    }
    post = ShowcasePost(
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
        publish_source="proxy",
        attribution=attribution,
        status=initial_status,
    )
    if initial_status == "approved":
        post.reviewed_by = current_user.id
        post.reviewed_at = datetime.now(UTC)

    db.add(post)
    await write_showcase_audit(
        db,
        actor_id=current_user.id,
        action="proxy_create",
        post_id=post_id,
        payload={
            "attribution": attribution,
            "auto_approve": auto_approve,
            "status": initial_status,
        },
    )
    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        await rollback_created_post_assets(
            post_id=post_id,
            thumbnail_path=thumbnail_path,
            spec=spec_obj,
            user_id=current_user.id,
            reason="proxy_db_commit_failed",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create proxy case",
        ) from exc
    await showcase_cache.invalidate_post(post_id)
    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Proxy case created",
        "post": await _format_post(post, current_user, db),
    }


class PurgeOrphansBody(BaseModel):
    """Body for orphan COS purge (dry_run defaults true)."""

    dry_run: bool = True


@router.get("/admin/showcase/storage/status")
async def admin_showcase_storage_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """COS / local storage health for Showcase media."""
    if not await can_view_showcase_dashboard(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient Showcase permission")
    return build_storage_status().to_dict()


@router.get("/admin/showcase/storage/reconcile")
async def admin_showcase_storage_reconcile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_VIEW)),
):
    """Diff Postgres media keys vs COS objects under the Showcase prefix."""
    if not await can_view_showcase_dashboard(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient Showcase permission")
    report = await reconcile_showcase_storage(db)
    return report.to_dict()


@router.post("/admin/showcase/storage/purge-orphans")
async def admin_showcase_storage_purge_orphans(
    body: PurgeOrphansBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_SHOWCASE_EDIT)),
):
    """
    Purge COS objects not referenced by any Showcase post.

    dry_run=true (default) only reports planned deletes.
    """
    perms = await load_user_showcase_permissions(db, current_user)
    if PERM_DELETE not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Showcase delete permission required to purge orphans",
        )
    return await purge_orphans_from_reconcile(db, dry_run=body.dry_run)
