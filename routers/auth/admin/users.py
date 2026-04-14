"""Admin User Management Endpoints.

Admin-only user management endpoints:
- GET /admin/users - List users with pagination
- PUT /admin/users/{user_id} - Update user
- DELETE /admin/users/{user_id} - Delete user
- PUT /admin/users/{user_id}/unlock - Unlock user account
- PUT /admin/users/{user_id}/reset-password - Reset user password

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional, cast
import logging

from fastapi import APIRouter, Depends, HTTPException, Body, Query, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce as sa_coalesce, count as sa_count, sum as sa_sum

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.diagrams import Diagram
from models.domain.messages import Messages, Language
from models.domain.token_usage import TokenUsage
from services.auth.password_security import (
    invalidate_user_cache_after_password_write,
    revoke_refresh_tokens_and_sessions,
)
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import hash_password

from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users_admin(
    db: AsyncSession = Depends(get_async_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str = Query(""),
    organization_id: Optional[int] = Query(None),
):
    """
    List users with pagination and filtering (ADMIN ONLY)

    Query Parameters:
    - page: Page number (starting from 1)
    - page_size: Number of items per page (default: 50)
    - search: Search by name or phone number
    - organization_id: Filter by organization
    """
    conditions = []
    if organization_id:
        conditions.append(User.organization_id == organization_id)
    if search:
        search_term = f"%{search}%"
        conditions.append((User.name.like(search_term)) | (User.phone.like(search_term)))

    total_stmt = select(sa_count()).select_from(User)
    list_stmt = select(User).order_by(User.created_at.desc())
    if conditions:
        filt = and_(*conditions)
        total_stmt = total_stmt.where(filt)
        list_stmt = list_stmt.where(filt)
    total = (await db.execute(total_stmt)).scalar_one()
    skip = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size

    list_stmt = list_stmt.offset(skip).limit(page_size)
    users = (await db.execute(list_stmt)).scalars().all()

    org_ids = {user.organization_id for user in users if user.organization_id}
    organizations_by_id = {}
    if org_ids:
        org_stmt = select(Organization).where(Organization.id.in_(org_ids))
        orgs = (await db.execute(org_stmt)).scalars().all()
        organizations_by_id = {cast(int, org.id): org for org in orgs}

    token_stats_by_user = {}

    try:
        token_stmt = (
            select(
                TokenUsage.user_id,
                sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            )
            .where(TokenUsage.success, TokenUsage.user_id.isnot(None))
            .group_by(TokenUsage.user_id)
        )
        user_token_stats = (await db.execute(token_stmt)).all()

        for stat in user_token_stats:
            token_stats_by_user[stat.user_id] = {
                "input_tokens": int(stat.input_tokens or 0),
                "output_tokens": int(stat.output_tokens or 0),
                "total_tokens": int(stat.total_tokens or 0),
            }
    except (ImportError, Exception) as e:
        logger.debug("TokenUsage not available yet: %s", e)

    result = []
    for user in users:
        org = organizations_by_id.get(user.organization_id) if user.organization_id else None

        masked_phone = user.phone
        if len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]

        user_token_stats = token_stats_by_user.get(user.id, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": user.name,
                "role": getattr(user, "role", "user") or "user",
                "organization_id": user.organization_id,
                "organization_code": org.code if org else None,
                "organization_name": org.name if org else None,
                "locked_until": utc_to_beijing_iso(user.locked_until),
                "created_at": utc_to_beijing_iso(user.created_at),
                "token_stats": user_token_stats,
                "email_login_whitelisted_from_cn": getattr(
                    user, "email_login_whitelisted_from_cn", False
                ),
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


@router.get("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def get_user_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Return one user's fields including full phone (ADMIN ONLY).

    List endpoints return masked phone; use this before editing a user.
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    org = None
    if user.organization_id:
        org = (
            await db.execute(select(Organization).where(Organization.id == user.organization_id))
        ).scalar_one_or_none()

    logger.info(
        "[Auth] Admin user_id=%s read full user profile for user_id=%s",
        current_user.id,
        user_id,
    )

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
        "email_login_whitelisted_from_cn": getattr(
            user, "email_login_whitelisted_from_cn", False
        ),
    }


@router.put("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def update_user_admin(
    user_id: int,
    request: dict,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Update user information (ADMIN ONLY)"""
    cached_user = await user_cache.get_by_id(user_id)
    if not cached_user:
        row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not row:
            error_msg = Messages.error("user_not_found", lang, user_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    old_phone = user.phone
    old_org_id = user.organization_id

    if "phone" in request:
        new_phone = request["phone"].strip()
        if not new_phone:
            error_msg = Messages.error("phone_cannot_be_empty", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_phone) != 11 or not new_phone.isdigit() or not new_phone.startswith("1"):
            error_msg = Messages.error("phone_format_invalid", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        if new_phone != user.phone:
            existing = await user_cache.get_by_phone(new_phone)
            if existing and existing.id != user.id:
                error_msg = Messages.error("phone_already_registered_other", lang, new_phone)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        user.phone = new_phone

    if "name" in request:
        new_name = request["name"].strip()
        if not new_name or len(new_name) < 2:
            error_msg = Messages.error("name_too_short", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if any(char.isdigit() for char in new_name):
            error_msg = Messages.error("name_cannot_contain_numbers", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        user.name = new_name

    if "email_login_whitelisted_from_cn" in request:
        raw_flag = request["email_login_whitelisted_from_cn"]
        if not isinstance(raw_flag, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="email_login_whitelisted_from_cn must be a boolean",
            )
        user.email_login_whitelisted_from_cn = raw_flag

    if "organization_id" in request:
        org_id = request["organization_id"]
        if org_id:
            org = await org_cache.get_by_id(org_id)
            if not org:
                org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
                if not org:
                    error_msg = Messages.error("organization_not_found", lang, org_id)
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
            user.organization_id = org_id

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to update user ID %s in database: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        ) from e

    try:
        user_cache.invalidate(user_id, old_phone, getattr(user, "email", None))
        logger.debug("[Auth] Invalidated old cache for user ID %s", user_id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate cache for user ID %s: %s", user_id, e)

    try:
        user_cache.cache_user(user)
        logger.info("[Auth] Updated and re-cached user ID %s", user_id)
    except Exception as e:
        logger.warning("[Auth] Failed to re-cache user ID %s: %s", user_id, e)

    if old_org_id != user.organization_id:
        try:
            if user.organization_id:
                new_org = await org_cache.get_by_id(user.organization_id)
                if new_org:
                    org_cache.invalidate(
                        user.organization_id,
                        cast(Optional[str], new_org.code),
                        cast(Optional[str], new_org.invitation_code),
                    )
            if old_org_id:
                old_org = await org_cache.get_by_id(old_org_id)
                if old_org:
                    org_cache.invalidate(
                        old_org_id,
                        cast(Optional[str], old_org.code),
                        cast(Optional[str], old_org.invitation_code),
                    )
        except Exception as e:
            logger.warning("[Auth] Failed to invalidate org cache: %s", e)

    org = await org_cache.get_by_id(user.organization_id) if user.organization_id else None
    if not org and user.organization_id:
        org = (
            await db.execute(select(Organization).where(Organization.id == user.organization_id))
        ).scalar_one_or_none()

    logger.info("Admin %s updated user: %s", current_user.phone, user.phone)

    return {
        "message": Messages.success("user_updated", lang),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None,
            "email_login_whitelisted_from_cn": getattr(
                user, "email_login_whitelisted_from_cn", False
            ),
        },
    }


@router.delete("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Delete user (ADMIN ONLY)"""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    if user.id == current_user.id:
        error_msg = Messages.error("cannot_delete_own_account", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    user_phone = user.phone

    try:
        await db.execute(delete(Diagram).where(Diagram.user_id == user_id))
        await db.delete(user)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to delete user ID %s in database: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        ) from e

    try:
        user_cache.invalidate(user_id, user_phone, getattr(user, "email", None))
        logger.info("[Auth] Invalidated cache for deleted user ID %s", user_id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate cache for deleted user ID %s: %s", user_id, e)

    logger.warning("Admin %s deleted user: %s", current_user.phone, user_phone)
    return {"message": Messages.success("user_deleted", lang, user_phone)}


@router.put("/admin/users/{user_id}/unlock", dependencies=[Depends(require_admin)])
async def unlock_user_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Unlock user account (ADMIN ONLY)"""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user.failed_login_attempts = 0
    user.locked_until = None

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to unlock user ID %s in database: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlock user",
        ) from e

    try:
        user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        user_cache.cache_user(user)
        logger.info("[Auth] Unlocked and re-cached user ID %s", user.id)
    except Exception as e:
        logger.warning("[Auth] Failed to update cache after unlock: %s", e)

    logger.info("Admin %s unlocked user: %s", current_user.phone, user.phone)
    return {"message": Messages.success("user_unlocked", lang, user.phone)}


@router.put("/admin/users/{user_id}/reset-password", dependencies=[Depends(require_admin)])
async def reset_user_password_admin(
    user_id: int,
    request: Optional[dict] = Body(None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Reset user password (ADMIN ONLY)

    Request body (optional):
        {
            "password": "new_password"  # Optional, defaults to "12345678" if not provided
        }

    Security:
        - Admin only
        - Cannot reset own password
        - Also unlocks account if locked
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    if user.id == current_user.id:
        error_msg = Messages.error("cannot_reset_own_password", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    password = request.get("password") if request and isinstance(request, dict) else None
    new_password = password if password and password.strip() else "12345678"

    if not new_password or len(new_password.strip()) == 0:
        error_msg = Messages.error("password_cannot_be_empty", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    if len(new_password.strip()) < 8:
        error_msg = Messages.error("password_too_short", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to reset password in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        ) from e

    invalidate_user_cache_after_password_write(user, "Admin password reset")
    revoke_refresh_tokens_and_sessions(user.id, "admin_password_reset")

    logger.info("Admin %s reset password for user: %s", current_user.phone, user.phone)
    return {"message": Messages.success("password_reset_for_user", lang, user.phone)}
