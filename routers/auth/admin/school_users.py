"""Org-scoped user management for the school dashboard (admin or school manager).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce as sa_coalesce, count as sa_count, sum as sa_sum

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Messages, Language
from models.domain.token_usage import TokenUsage
from services.auth.phone_uniqueness import other_user_id_with_phone
from services.auth.school_dashboard_logger import get_school_dashboard_logger
from services.auth.user_fk_cleanup import delete_user_fk_dependent_rows
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache

from ..dependencies import get_language_dependency, require_admin_or_manager
from ..helpers import utc_to_beijing_iso
from .school_scope import resolve_school_dashboard_org_id

logger = logging.getLogger(__name__)

router = APIRouter()

_SCHOOL_USER_ALLOWED_BODY_KEYS = frozenset({"name", "phone"})


async def _load_user_in_school_or_not_found(
    db: AsyncSession,
    user_id: int,
    effective_org_id: int,
) -> Optional[User]:
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if row is None or row.organization_id != effective_org_id:
        return None
    return row


def _not_found_school_user(lang: Language) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=Messages.error("school_user_not_found", lang=lang),
    )


@router.get("/admin/school/users", dependencies=[Depends(require_admin_or_manager)])
async def list_school_users(
    organization_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str = Query(""),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    """
    List users in a single organization (school dashboard only).
    Admins: pass organization_id. Managers: scoped to their org.
    """
    org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)
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
        except Exception as exc:
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

    result = []
    for user in users:
        masked_phone = user.phone
        if user.phone and len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]

        tstat = token_stats_by_user.get(user.id, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": user.name,
                "role": getattr(user, "role", "user") or "user",
                "organization_id": user.organization_id,
                "organization_code": org_row.code if org_row else None,
                "organization_name": org_row.name if org_row else None,
                "locked_until": utc_to_beijing_iso(user.locked_until),
                "created_at": utc_to_beijing_iso(user.created_at),
                "token_stats": tstat,
                "email_login_whitelisted_from_cn": getattr(user, "email_login_whitelisted_from_cn", False),
            }
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


@router.get("/admin/school/users/{user_id}", dependencies=[Depends(require_admin_or_manager)])
async def get_school_user(
    user_id: int,
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
    org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)
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

    return {
        "id": user.id,
        "phone": user.phone,
        "name": user.name,
        "role": getattr(user, "role", "user") or "user",
        "organization_id": user.organization_id,
        "organization_code": org.code if org else None,
        "organization_name": org.name if org else None,
        "locked_until": utc_to_beijing_iso(user.locked_until),
        "created_at": utc_to_beijing_iso(user.created_at),
        "email_login_whitelisted_from_cn": getattr(user, "email_login_whitelisted_from_cn", False),
    }


@router.put("/admin/school/users/{user_id}", dependencies=[Depends(require_admin_or_manager)])
async def update_school_user(
    user_id: int,
    request: dict,
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, Any]:
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

    org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)
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
            if await other_user_id_with_phone(db, new_phone, user.id) is not None:
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
    except Exception as e:
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
    except Exception as e:
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


@router.delete("/admin/school/users/{user_id}", dependencies=[Depends(require_admin_or_manager)])
async def delete_school_user(
    user_id: int,
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, str]:
    org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)
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
    except Exception as e:
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
    except Exception as e:
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


@router.put(
    "/admin/school/users/{user_id}/unlock",
    dependencies=[Depends(require_admin_or_manager)],
)
async def unlock_school_user(
    user_id: int,
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
) -> dict[str, str]:
    org_id = resolve_school_dashboard_org_id(organization_id, current_user, lang)
    user = await _load_user_in_school_or_not_found(db, user_id, org_id)
    if not user:
        raise _not_found_school_user(lang)

    sd_log = get_school_dashboard_logger(logger, actor_id=current_user.id, org_id=org_id, target_user_id=user_id)

    user.failed_login_attempts = 0
    user.locked_until = None
    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
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
    except Exception as e:
        sd_log.warning(
            "school unlock cache failed: %s",
            e,
            extra={"sd_event": "school_user_unlock_cache_failed", "sd_error_type": type(e).__name__},
        )

    sd_log.info("[SchoolDashboard] user unlocked", extra={"sd_event": "school_user_unlocked"})
    return {"message": Messages.success("user_unlocked", lang, user.phone)}
