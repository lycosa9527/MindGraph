"""Org-scoped user management for the school dashboard (admin or school manager).

Reference implementation for "super-admin OR school manager": uses
``require_panel_capability(CAP_TAB_USERS_VIEW|EDIT)`` + ``AdminScope`` org filtering.
See ``routers/auth/admin/users.py`` for global super-admin-only user ops.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce as sa_coalesce
from sqlalchemy.sql.functions import count as sa_count
from sqlalchemy.sql.functions import sum as sa_sum

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages
from models.domain.token_usage import TokenUsage
from services.auth.admin_user_list_rows import (
    build_admin_user_detail_payload,
    diagram_quota_for_user,
    enrich_admin_user_list_rows,
)
from utils.auth.user_daily_token_quota import resolve_daily_usage
from services.auth.phone_uniqueness import other_user_id_with_phone
from services.auth.school_dashboard_logger import get_school_dashboard_logger
from services.auth.school_user_create import (
    batch_result_payload,
    create_school_member_batch,
    create_school_member_user,
    parse_school_member_batch,
    parse_school_member_input,
)
from services.auth.user_fk_cleanup import delete_user_fk_dependent_rows
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from services.utils.error_types import DATABASE_ERRORS, REDIS_ERRORS
from utils.auth.admin_panel_permissions import CAP_TAB_USERS_EDIT, CAP_TAB_USERS_VIEW
from utils.auth.admin_scope import AdminScope

from ..dependencies import get_language_dependency, require_panel_capability
from ..helpers import commit_user_with_retry
from .school_scope import resolve_school_dashboard_org_id_scoped

logger = logging.getLogger(__name__)

router = APIRouter()

_SCHOOL_USER_ALLOWED_BODY_KEYS = frozenset({"name", "phone", "email"})


async def _load_user_in_school_or_not_found(
    db: AsyncSession,
    user_id: int,
    effective_org_id: int,
) -> Optional[User]:
    """Load user in school or not found."""
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if row is None or row.organization_id != effective_org_id:
        return None
    return row


def _not_found_school_user(lang: Language) -> HTTPException:
    """Not found school user."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=Messages.error("school_user_not_found", lang=lang),
    )


@router.get("/admin/school/users")
async def list_school_users(
    organization_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str = Query(""),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_VIEW)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """
    List users in a single organization (school dashboard only).
    Admins: pass organization_id. Managers: scoped to their org.
    """
    current_user = scope.actor
    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id)

    conditions: list[Any] = [User.organization_id == org_id]
    if search:
        search_term = f"%{search}%"
        conditions.append((User.name.like(search_term)) | (User.phone.like(search_term)))

    filt = and_(*conditions)
    total_stmt = select(sa_count()).select_from(User).where(filt)
    list_stmt = select(User).where(filt).order_by(User.created_at.desc())
    total = (await db.execute(total_stmt)).scalar_one()
    skip = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size
    list_stmt = list_stmt.offset(skip).limit(page_size)
    users = (await db.execute(list_stmt)).scalars().all()

    org_row = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()

    token_stats_by_user: dict[int, dict[str, int]] = {}
    if users:
        try:
            uids = [u.id for u in users]
            token_stmt = (
                select(
                    TokenUsage.user_id,
                    sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                )
                .where(
                    TokenUsage.success,
                    TokenUsage.user_id.isnot(None),
                    TokenUsage.user_id.in_(uids),
                )
                .group_by(TokenUsage.user_id)
            )
            user_token_stats = (await db.execute(token_stmt)).all()
            for stat in user_token_stats:
                token_stats_by_user[stat.user_id] = {
                    "input_tokens": int(stat.input_tokens or 0),
                    "output_tokens": int(stat.output_tokens or 0),
                    "total_tokens": int(stat.total_tokens or 0),
                }
        except DATABASE_ERRORS as exc:
            sd_log.debug(
                "TokenUsage not available for school list: %s",
                exc,
                extra={"sd_event": "school_users_token_aggregate_skipped"},
            )

    sd_log.debug(
        "[SchoolDashboard] users listed page=%s page_size=%s total=%s",
        page,
        page_size,
        total,
        extra={"sd_event": "school_users_list", "sd_search_len": len(search)},
    )

    organizations_by_id = {int(org_row.id): org_row} if org_row else {}
    result = await enrich_admin_user_list_rows(
        db,
        users,
        organizations_by_id,
        token_stats_by_user,
    )

    return {
        "users": result,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.post("/admin/school/users")
async def create_school_user(
    request: dict,
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """Create school user."""
    current_user = scope.actor
    if not isinstance(request, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang=lang),
        )

    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, org_id),
        )

    member = parse_school_member_input(request, lang, actor_role=getattr(current_user, "role", None))
    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id)

    try:
        new_user = await create_school_member_user(db, org, member, lang)
        await commit_user_with_retry(db, new_user, max_retries=5, lang=lang)
    except HTTPException:
        await db.rollback()
        raise
    except DATABASE_ERRORS as exc:
        await db.rollback()
        sd_log.error(
            "school user create failed: %s",
            exc,
            extra={"sd_event": "school_user_create_failed", "sd_error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("user_creation_failed", lang=lang),
        ) from exc

    try:
        await user_cache.cache_user(new_user)
    except REDIS_ERRORS as exc:
        sd_log.warning(
            "school user cache write failed: %s",
            exc,
            extra={"sd_event": "school_user_create_cache_failed", "sd_error_type": type(exc).__name__},
        )

    sd_log.info(
        "[SchoolDashboard] user created phone=%s",
        new_user.phone,
        extra={"sd_event": "school_user_created", "sd_target_user_id": new_user.id},
    )
    return {
        "message": Messages.success("school_user_created", lang=lang),
        "user": {
            "id": new_user.id,
            "phone": new_user.phone,
            "email": new_user.email,
            "name": new_user.name,
            "role": new_user.role,
        },
    }


@router.post("/admin/school/users/batch")
async def create_school_users_batch(
    request: dict,
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """Create school users batch."""
    current_user = scope.actor
    if not isinstance(request, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang=lang),
        )

    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, org_id),
        )

    members, parse_failed = parse_school_member_batch(
        request.get("members"),
        lang,
        actor_role=getattr(current_user, "role", None),
    )
    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id)

    try:
        created, create_failed, skipped_count = await create_school_member_batch(db, org, members, lang)
        failed = parse_failed + create_failed
        if created:
            await db.commit()
            for user in created:
                await db.refresh(user)
        else:
            await db.rollback()
    except HTTPException:
        await db.rollback()
        raise
    except DATABASE_ERRORS as exc:
        await db.rollback()
        sd_log.error(
            "school user batch create failed: %s",
            exc,
            extra={"sd_event": "school_user_batch_create_failed", "sd_error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("user_creation_failed", lang=lang),
        ) from exc

    for user in created:
        try:
            await user_cache.cache_user(user)
        except REDIS_ERRORS as exc:
            sd_log.warning(
                "school user batch cache write failed: %s",
                exc,
                extra={"sd_event": "school_user_create_cache_failed", "sd_error_type": type(exc).__name__},
            )

    sd_log.info(
        "[SchoolDashboard] batch created count=%s failed=%s skipped=%s",
        len(created),
        len(failed),
        skipped_count,
        extra={"sd_event": "school_user_batch_created"},
    )
    return batch_result_payload(created, failed, lang, skipped_count=skipped_count)


@router.get("/admin/school/users/{user_id}")
async def get_school_user(
    user_id: int,
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_VIEW)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """Get school user."""
    current_user = scope.actor
    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    user = await _load_user_in_school_or_not_found(db, user_id, org_id)
    if not user:
        raise _not_found_school_user(lang)

    org = None
    if user.organization_id:
        org = (
            await db.execute(select(Organization).where(Organization.id == user.organization_id))
        ).scalar_one_or_none()

    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id, target_user_id=user_id)
    sd_log.info("[SchoolDashboard] user read", extra={"sd_event": "school_user_read"})

    diagram_counts = await diagram_quota_for_user(db, user_id)
    token_used_today = await resolve_daily_usage(user_id)
    return build_admin_user_detail_payload(
        user,
        org,
        diagram_counts["diagram_count"],
        token_used_today=token_used_today,
    )


@router.put("/admin/school/users/{user_id}")
async def update_school_user(
    user_id: int,
    request: dict,
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """Update school user."""
    current_user = scope.actor
    if not isinstance(request, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang=lang),
        )

    extra_keys = set(request.keys()) - _SCHOOL_USER_ALLOWED_BODY_KEYS
    if extra_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_update_invalid_fields", lang=lang),
        )

    has_phone = "phone" in request and request.get("phone") is not None
    has_name = "name" in request and request.get("name") is not None
    if not has_phone and not has_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_update_empty", lang=lang),
        )

    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    user = await _load_user_in_school_or_not_found(db, user_id, org_id)
    if not user:
        raise _not_found_school_user(lang)

    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id, target_user_id=user_id)

    old_phone = user.phone
    phone_will_change = False
    last_requested_new_phone: Optional[str] = None
    if "phone" in request and request["phone"] is not None:
        new_phone = str(request["phone"]).strip()
        if not new_phone:
            error_msg = Messages.error("phone_cannot_be_empty", lang=lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_phone) != 11 or not new_phone.isdigit() or not new_phone.startswith("1"):
            error_msg = Messages.error("phone_format_invalid", lang=lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if new_phone != user.phone:
            if await other_user_id_with_phone(new_phone, user.id) is not None:
                error_msg = Messages.error("phone_already_registered_other", lang, new_phone)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
            phone_will_change = True
        last_requested_new_phone = new_phone
        user.phone = new_phone

    if "name" in request and request["name"] is not None:
        new_name = str(request["name"]).strip()
        if not new_name or len(new_name) < 2:
            error_msg = Messages.error("name_too_short", lang=lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if any(char.isdigit() for char in new_name):
            error_msg = Messages.error("name_cannot_contain_numbers", lang=lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        user.name = new_name

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as err:
        await db.rollback()
        if phone_will_change and last_requested_new_phone:
            sd_log.info(
                "school user phone unique constraint: %s",
                err,
                extra={
                    "sd_event": "school_user_update_phone_conflict",
                    "sd_error_type": type(err).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=Messages.error("phone_already_registered_other", lang, last_requested_new_phone),
            ) from err
        sd_log.error(
            "school user update failed: %s",
            err,
            extra={"sd_event": "school_user_update_failed", "sd_error_type": type(err).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("internal_error", lang=lang),
        ) from err
    except DATABASE_ERRORS as e:
        await db.rollback()
        sd_log.error(
            "school user update failed: %s",
            e,
            extra={"sd_event": "school_user_update_failed", "sd_error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("internal_error", lang=lang),
        ) from e

    try:
        await user_cache.invalidate(user_id, old_phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
    except REDIS_ERRORS as e:
        sd_log.warning(
            "school user cache update failed: %s",
            e,
            extra={"sd_event": "school_user_cache_write_failed", "sd_error_type": type(e).__name__},
        )

    org = None
    if user.organization_id:
        org = await org_cache.get_by_id(user.organization_id)
    if not org and user.organization_id:
        org = (
            await db.execute(select(Organization).where(Organization.id == user.organization_id))
        ).scalar_one_or_none()

    sd_log.info("[SchoolDashboard] user updated", extra={"sd_event": "school_user_updated"})

    return {
        "message": Messages.success("user_updated", lang=lang),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None,
            "email_login_whitelisted_from_cn": getattr(user, "email_login_whitelisted_from_cn", False),
        },
    }


@router.delete("/admin/school/users/{user_id}")
async def delete_school_user(
    user_id: int,
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, str]:
    """Delete school user."""
    current_user = scope.actor
    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    user = await _load_user_in_school_or_not_found(db, user_id, org_id)
    if not user:
        raise _not_found_school_user(lang)

    if user.id == current_user.id:
        error_msg = Messages.error("cannot_delete_own_account", lang=lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    user_phone = user.phone
    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id, target_user_id=user_id)
    try:
        await delete_user_fk_dependent_rows(db, user_id)
        await db.delete(user)
        await db.commit()
    except DATABASE_ERRORS as e:
        await db.rollback()
        sd_log.error(
            "school user delete failed: %s",
            e,
            extra={"sd_event": "school_user_delete_failed", "sd_error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("internal_error", lang=lang),
        ) from e

    try:
        await user_cache.invalidate(user_id, user_phone, getattr(user, "email", None))
    except REDIS_ERRORS as e:
        sd_log.warning(
            "cache invalidate after school delete failed: %s",
            e,
            extra={
                "sd_event": "school_user_delete_cache_failed",
                "sd_error_type": type(e).__name__,
            },
        )

    sd_log.warning(
        "[SchoolDashboard] user deleted actor_phone=%s",
        current_user.phone,
        extra={"sd_event": "school_user_deleted"},
    )
    return {"message": Messages.success("user_deleted", lang, user_phone)}


@router.put("/admin/school/users/{user_id}/unlock")
async def unlock_school_user(
    user_id: int,
    organization_id: Optional[int] = Query(None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, str]:
    """Unlock school user."""
    current_user = scope.actor
    org_id = await resolve_school_dashboard_org_id_scoped(scope, organization_id, db, lang)
    user = await _load_user_in_school_or_not_found(db, user_id, org_id)
    if not user:
        raise _not_found_school_user(lang)

    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id, target_user_id=user_id)

    user.failed_login_attempts = 0
    user.locked_until = None
    try:
        await db.commit()
        await db.refresh(user)
    except DATABASE_ERRORS as e:
        await db.rollback()
        sd_log.error(
            "school unlock failed: %s",
            e,
            extra={"sd_event": "school_user_unlock_failed", "sd_error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("internal_error", lang=lang),
        ) from e

    try:
        await user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
    except REDIS_ERRORS as e:
        sd_log.warning(
            "school unlock cache failed: %s",
            e,
            extra={"sd_event": "school_user_unlock_cache_failed", "sd_error_type": type(e).__name__},
        )

    sd_log.info("[SchoolDashboard] user unlocked", extra={"sd_event": "school_user_unlocked"})
    return {"message": Messages.success("user_unlocked", lang, user.phone)}
