"""Case Square routes: list, create/update, detail, and lifecycle."""

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
from models.domain.case_square import CaseSquarePost, CaseSquarePostFavorite, CaseSquarePostLike
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.case_square_common import (
    _apply_author_case_update,
    _delete_case_post_with_panel_rls,
    _form_flag_true,
    _format_post,
    _increment_approved_post_views,
    _load_post_for_format,
    _safe_case_square_audit,
    _search_filter,
    _validate_case_type,
    _validate_optional_diagram_type,
    _validate_optional_filter_text,
    _validate_optional_publish_source,
    _validate_post_id,
    _validate_sort,
)
from routers.features.case_square_constants import CASE_STATUSES
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
    delete_spec_json,
    delete_thumbnail,
    parse_tags_json,
    prepare_post_id_and_spec,
    resolve_gallery_image_uploads,
    save_case_file,
    save_spec_json,
    save_thumbnail_from_upload,
    validate_gallery_spec,
)
from routers.features.case_square_permissions import (
    can_delete_case,
    can_delist_case,
    can_edit_case,
    can_publish_case,
    can_review_case,
    can_view_non_approved_post,
    can_withdraw_case,
)
from services.case_square.field_options import validate_grade, validate_subject
from services.case_square.post_delete import case_square_post_still_exists, delete_case_square_post_rows
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.db.rls_context import RlsContext, apply_rls_context_async

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


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return a single case by ID (increments views when approved)."""
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
