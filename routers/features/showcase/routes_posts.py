"""Showcase routes: list, create/update, detail, and lifecycle."""

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.auth import User
from models.domain.showcase import ShowcasePost, ShowcasePostFavorite, ShowcasePostLike
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.field_options import validate_grade, validate_subject
from services.showcase.post_delete import (
    clear_showcase_post_engagement,
    delete_showcase_post_rows,
    showcase_post_still_exists,
)
from services.showcase.posts.lifecycle import (
    log_cache_invalidate,
    log_create_success,
    log_delete,
    log_withdraw,
    rollback_created_post_assets,
)
from services.showcase.storage import delete_post_assets
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.db.rls_context import RlsContext, apply_rls_context_async

from .common import (
    _apply_author_case_update,
    _delete_case_post_with_panel_rls,
    _form_flag_true,
    _format_post,
    _increment_approved_post_views,
    _load_post_for_format,
    _safe_showcase_audit,
    _search_filter,
    _validate_case_type,
    _validate_optional_diagram_type,
    _validate_optional_filter_text,
    _validate_optional_publish_source,
    _validate_post_id,
    _validate_sort,
)
from .constants import CASE_STATUSES
from .helpers import (
    ALLOWED_DOC_SUFFIXES,
    ALLOWED_SOURCE_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    ATTACHMENT_MAX_BYTES,
    VIDEO_MAX_BYTES,
    apply_gallery_image_uploads,
    assert_gallery_uploads_resolved,
    collect_gallery_images_from_request,
    count_pending_gallery_images,
    parse_tags_json,
    prepare_post_id_and_spec,
    resolve_gallery_image_uploads,
    save_case_file,
    save_spec_json,
    save_thumbnail_from_upload,
    validate_gallery_spec,
)
from .permissions import (
    can_delete_case,
    can_delist_case,
    can_edit_case,
    can_publish_case,
    can_review_case,
    can_view_non_approved_post,
    can_withdraw_case,
)
from .routes_uploads import reject_if_cos_multipart_files_present

logger = logging.getLogger(__name__)

router = APIRouter()


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
    """List showcase posts. Public feed shows approved only."""
    cacheable = (
        not mine
        and not favorited
        and not search
        and not status_filter
        and not expert_recommended
        and not publish_source
        and not diagram_type
    )
    if cacheable:
        cached = await showcase_cache.get_cached_list(
            user_id=current_user.id,
            mine=False,
            case_type=case_type,
            subject=subject,
            grade=grade,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        if cached is not None:
            return cached
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
        filters.append(ShowcasePost.status == "approved")
    elif mine:
        filters.append(ShowcasePost.author_id == current_user.id)
    elif status_filter and await can_review_case(db, current_user):
        filters.append(ShowcasePost.status == status_filter)
    else:
        filters.append(ShowcasePost.status == "approved")

    if case_type:
        filters.append(ShowcasePost.case_type == case_type)
    if expert_recommended:
        filters.append(ShowcasePost.is_expert_recommended.is_(True))
    if subject:
        filters.append(ShowcasePost.subject == subject)
    if grade:
        filters.append(ShowcasePost.grade == grade)
    if diagram_type:
        filters.append(ShowcasePost.diagram_type == diagram_type)
    if publish_source:
        filters.append(ShowcasePost.publish_source == publish_source)
    if search and search.strip():
        filters.append(_search_filter(search))

    count_stmt = select(sa_count()).select_from(ShowcasePost)
    if favorite_join:
        count_stmt = count_stmt.join(
            ShowcasePostFavorite,
            (ShowcasePostFavorite.post_id == ShowcasePost.id) & (ShowcasePostFavorite.user_id == current_user.id),
        )
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(ShowcasePost).options(
        joinedload(ShowcasePost.author).joinedload(User.organization),
        joinedload(ShowcasePost.reviewer),
        joinedload(ShowcasePost.expert_recommender),
    )
    if favorite_join:
        stmt = stmt.join(
            ShowcasePostFavorite,
            (ShowcasePostFavorite.post_id == ShowcasePost.id) & (ShowcasePostFavorite.user_id == current_user.id),
        )
    if filters:
        stmt = stmt.where(*filters)

    if favorited:
        stmt = stmt.order_by(ShowcasePostFavorite.created_at.desc())
    elif sort == "hot":
        stmt = stmt.order_by(
            ShowcasePost.is_expert_recommended.desc(),
            (ShowcasePost.likes_count + ShowcasePost.views_count).desc(),
            ShowcasePost.created_at.desc(),
        )
    elif sort == "newest":
        stmt = stmt.order_by(ShowcasePost.created_at.desc())
    elif sort == "oldest":
        stmt = stmt.order_by(ShowcasePost.created_at.asc())
    elif sort == "title_asc":
        stmt = stmt.order_by(ShowcasePost.title.asc(), ShowcasePost.created_at.desc())
    elif sort == "title_desc":
        stmt = stmt.order_by(ShowcasePost.title.desc(), ShowcasePost.created_at.desc())
    elif sort == "subject_asc":
        stmt = stmt.order_by(
            ShowcasePost.subject.asc().nulls_last(),
            ShowcasePost.created_at.desc(),
        )
    elif sort == "subject_desc":
        stmt = stmt.order_by(
            ShowcasePost.subject.desc().nulls_last(),
            ShowcasePost.created_at.desc(),
        )
    elif sort == "grade_asc":
        stmt = stmt.order_by(
            ShowcasePost.grade.asc().nulls_last(),
            ShowcasePost.created_at.desc(),
        )
    elif sort == "grade_desc":
        stmt = stmt.order_by(
            ShowcasePost.grade.desc().nulls_last(),
            ShowcasePost.created_at.desc(),
        )
    elif sort == "reviewed_newest":
        stmt = stmt.order_by(
            ShowcasePost.reviewed_at.desc().nulls_last(),
            ShowcasePost.created_at.desc(),
        )
    elif sort == "reviewed_oldest":
        stmt = stmt.order_by(
            ShowcasePost.reviewed_at.asc().nulls_last(),
            ShowcasePost.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(
            ShowcasePost.is_expert_recommended.desc(),
            ShowcasePost.created_at.desc(),
        )

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    posts = (await db.execute(stmt)).unique().scalars().all()

    liked_post_ids: Set[str] = set()
    if posts:
        post_ids = [p.id for p in posts]
        liked_rows = (
            await db.execute(
                select(ShowcasePostLike.post_id).where(
                    ShowcasePostLike.user_id == current_user.id,
                    ShowcasePostLike.post_id.in_(post_ids),
                )
            )
        ).all()
        liked_post_ids = {row[0] for row in liked_rows}
        favorited_rows = (
            await db.execute(
                select(ShowcasePostFavorite.post_id).where(
                    ShowcasePostFavorite.user_id == current_user.id,
                    ShowcasePostFavorite.post_id.in_(post_ids),
                )
            )
        ).all()
        favorited_post_ids = {row[0] for row in favorited_rows}
    else:
        favorited_post_ids = set()

    formatted = [await _format_post(p, current_user, db, liked_post_ids, favorited_post_ids) for p in posts]
    payload = {
        "posts": formatted,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
    }
    if cacheable:
        await showcase_cache.set_cached_list(
            payload,
            user_id=current_user.id,
            mine=False,
            case_type=case_type,
            subject=subject,
            grade=grade,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    return payload


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
    logger.info("[Showcase] create_post user=%s case_type=%s", current_user.id, case_type)
    if not await can_publish_case(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot publish cases")

    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("showcase_create", identifier, max_requests=20, window_seconds=60)

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
                logger.warning("[Showcase] Failed to save teaching thumbnail for %s: %s", post_id, err)
                await rollback_created_post_assets(
                    post_id=post_id,
                    thumbnail_path=thumbnail_path,
                    spec=spec_obj,
                    user_id=current_user.id,
                    reason="thumbnail_save_failed",
                )
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
                reject_if_cos_multipart_files_present(True)
                logger.info(
                    "[Showcase] create_post gallery_images=%s pending=%s post=%s",
                    len(resolved_gallery),
                    pending_images,
                    post_id,
                )
                await apply_gallery_image_uploads(post_id, spec_obj, resolved_gallery)
                assert_gallery_uploads_resolved(spec_obj)
            elif pending_images:
                logger.warning(
                    "[Showcase] create_post gallery pending=%s but no gallery_images received post=%s",
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
                logger.warning("[Showcase] Failed to save thumbnail for %s: %s", post_id, err)
                await rollback_created_post_assets(
                    post_id=post_id,
                    thumbnail_path=thumbnail_path,
                    spec=spec_obj,
                    user_id=current_user.id,
                    reason="thumbnail_save_failed",
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save thumbnail",
                ) from err

    if spec_obj:
        save_spec_json(post_id, spec_obj)

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
        publish_source="self",
        status="pending",
    )
    db.add(post)
    try:
        await db.commit()
        await db.refresh(post)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        await rollback_created_post_assets(
            post_id=post_id,
            thumbnail_path=thumbnail_path,
            spec=spec_obj,
            user_id=current_user.id,
            reason="db_commit_failed",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create case",
        ) from exc

    await showcase_cache.invalidate_post(post_id)
    log_cache_invalidate(post_id=post_id)
    log_create_success(post_id=post_id, user_id=current_user.id, case_type=case_type)
    logger.info(
        "[Showcase] create_post ok post=%s user=%s case_type=%s",
        post_id,
        current_user.id,
        case_type,
    )
    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Case submitted for review",
        "post": await _format_post(post, current_user, db),
    }


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
    await check_endpoint_rate_limit("showcase_update", identifier, max_requests=20, window_seconds=60)

    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
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

    resolved_gallery = await resolve_gallery_image_uploads(gallery_images, request)
    if resolved_gallery:
        reject_if_cos_multipart_files_present(True)
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

    await showcase_cache.invalidate_post(post_id)
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
    await check_endpoint_rate_limit("showcase_update", identifier, max_requests=20, window_seconds=60)

    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
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
    reject_if_cos_multipart_files_present(True)

    spec_obj = post.spec if isinstance(post.spec, dict) else None
    if not spec_obj or not isinstance(spec_obj.get("gallery"), list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case has no gallery to attach images to",
        )

    logger.info(
        "[Showcase] upload_post_gallery_images post=%s files=%s",
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

    await showcase_cache.invalidate_post(post_id)
    post = await _load_post_for_format(db, post_id)
    return {
        "message": "Gallery images uploaded",
        "post": await _format_post(post, current_user, db),
    }


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return a single case by ID (increments views when approved)."""
    _validate_post_id(post_id)
    stmt = (
        select(ShowcasePost)
        .options(
            joinedload(ShowcasePost.author).joinedload(User.organization),
            joinedload(ShowcasePost.reviewer),
            joinedload(ShowcasePost.expert_recommender),
        )
        .where(ShowcasePost.id == post_id)
    )
    post = (await db.execute(stmt)).unique().scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if post.status != "approved":
        if not await can_view_non_approved_post(post, current_user, db):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if post.status == "approved":
        bumped_views = await _increment_approved_post_views(post_id)
        await showcase_cache.invalidate_post(post_id)
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


async def _withdraw_case_post_handler(
    post_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, str]:
    _validate_post_id(post_id)
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not can_withdraw_case(post, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot withdraw this case")

    thumb_path = post.thumbnail_path
    spec_snapshot = dict(post.spec) if isinstance(post.spec, dict) else None

    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)
    try:
        await _safe_showcase_audit(
            db,
            actor_id=current_user.id,
            action="withdraw",
            post_id=post_id,
            payload={"title": post.title},
        )
        removed = await delete_showcase_post_rows(db, post_id)
        if removed != 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to withdraw case",
            )
        await db.commit()
        if await showcase_post_still_exists(db, post_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to withdraw case",
            )
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Showcase] Withdraw failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to withdraw case",
        ) from exc
    await delete_post_assets(post_id=post_id, thumbnail_path=thumb_path, spec=spec_snapshot)
    await showcase_cache.invalidate_post(post_id)
    log_withdraw(post_id=post_id, user_id=current_user.id)
    log_cache_invalidate(post_id=post_id)
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
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not can_delist_case(post, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delist this case")

    now = datetime.now(UTC)
    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)
    try:
        await _safe_showcase_audit(
            db,
            actor_id=current_user.id,
            action="delist",
            post_id=post_id,
            payload={"title": post.title},
        )
        await clear_showcase_post_engagement(db, post_id)
        post.status = "withdrawn"
        post.likes_count = 0
        post.is_expert_recommended = False
        post.expert_recommended_by = None
        post.expert_recommended_at = None
        post.updated_at = now
        await db.commit()
        await db.refresh(post)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Showcase] Delist failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delist case",
        ) from exc

    await showcase_cache.invalidate_post(post_id)
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


async def _delete_case_post_handler(
    post_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict[str, str]:
    _validate_post_id(post_id)
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not await can_delete_case(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete this case")

    thumb_path = post.thumbnail_path
    spec_snapshot = dict(post.spec) if isinstance(post.spec, dict) else None

    await _delete_case_post_with_panel_rls(
        db,
        post_id,
        actor=current_user,
        title=post.title,
    )

    await delete_post_assets(post_id=post_id, thumbnail_path=thumb_path, spec=spec_snapshot)
    await showcase_cache.invalidate_post(post_id)
    log_delete(post_id=post_id, user_id=current_user.id)
    log_cache_invalidate(post_id=post_id)
    return {"message": "Case deleted"}


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Hard-delete a case the caller is allowed to remove."""
    return await _delete_case_post_handler(post_id, current_user, db)


@router.post("/posts/{post_id}/delete")
async def delete_post_via_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """POST alias for environments that block or omit DELETE route registration."""
    return await _delete_case_post_handler(post_id, current_user, db)
