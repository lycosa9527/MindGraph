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
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Body, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import Organization, User
from models.domain.messages import Messages, Language
from models.domain.token_usage import TokenUsage
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import hash_password

from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso





logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users_admin(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str = Query(""),
    organization_id: Optional[int] = Query(None)
):
    """
    List users with pagination and filtering (ADMIN ONLY)

    Query Parameters:
    - page: Page number (starting from 1)
    - page_size: Number of items per page (default: 50)
    - search: Search by name or phone number
    - organization_id: Filter by organization
    """
    # Build base query
    query = db.query(User)

    # Apply organization filter
    if organization_id:
        query = query.filter(User.organization_id == organization_id)

    # Apply search filter (name or phone)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.name.like(search_term)) | (User.phone.like(search_term))
        )

    # Get total count for pagination
    total = query.count()

    # Calculate pagination
    skip = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size

    # Get paginated users
    users = query.order_by(User.created_at.desc()).offset(skip).limit(page_size).all()

    # Performance optimization: Fetch all organizations in one query
    org_ids = {user.organization_id for user in users if user.organization_id}
    organizations_by_id = {}
    if org_ids:
        orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all()
        organizations_by_id = {org.id: org for org in orgs}

    # Get token stats for all users
    token_stats_by_user = {}

    try:
        user_token_stats = db.query(
            TokenUsage.user_id,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens')
        ).filter(
            TokenUsage.success,
            TokenUsage.user_id.isnot(None)
        ).group_by(
            TokenUsage.user_id
        ).all()

        for stat in user_token_stats:
            token_stats_by_user[stat.user_id] = {
                "input_tokens": int(stat.input_tokens or 0),
                "output_tokens": int(stat.output_tokens or 0),
                "total_tokens": int(stat.total_tokens or 0)
            }
    except (ImportError, Exception) as e:
        logger.debug("TokenUsage not available yet: %s", e)

    result = []
    for user in users:
        org = organizations_by_id.get(user.organization_id) if user.organization_id else None

        # Mask phone number for privacy
        masked_phone = user.phone
        if len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]

        user_token_stats = token_stats_by_user.get(user.id, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        })

        result.append({
            "id": user.id,
            "phone": masked_phone,
            "phone_real": user.phone,
            "name": user.name,
            "role": getattr(user, 'role', 'user') or 'user',
            "organization_id": user.organization_id,
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None,
            "locked_until": utc_to_beijing_iso(user.locked_until),
            "created_at": utc_to_beijing_iso(user.created_at),
            "token_stats": user_token_stats
        })

    return {
        "users": result,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }


@router.put("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def update_user_admin(
    user_id: int,
    request: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Update user information (ADMIN ONLY)"""
    # Check if user exists (use cache for quick check)
    cached_user = user_cache.get_by_id(user_id)
    if not cached_user:
        # Check database as fallback
        cached_user = db.query(User).filter(User.id == user_id).first()
        if not cached_user:
            error_msg = Messages.error("user_not_found", lang, user_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Reload from database for modification (cached users are detached)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Save old values for cache invalidation
    old_phone = user.phone
    old_org_id = user.organization_id

    # Update phone (with validation)
    if "phone" in request:
        new_phone = request["phone"].strip()
        if not new_phone:
            error_msg = Messages.error("phone_cannot_be_empty", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_phone) != 11 or not new_phone.isdigit() or not new_phone.startswith('1'):
            error_msg = Messages.error("phone_format_invalid", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        if new_phone != user.phone:
            existing = user_cache.get_by_phone(new_phone)
            if existing and existing.id != user.id:
                error_msg = Messages.error("phone_already_registered_other", lang, new_phone)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        user.phone = new_phone

    # Update name (with validation)
    if "name" in request:
        new_name = request["name"].strip()
        if not new_name or len(new_name) < 2:
            error_msg = Messages.error("name_too_short", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if any(char.isdigit() for char in new_name):
            error_msg = Messages.error("name_cannot_contain_numbers", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        user.name = new_name

    # Update organization
    if "organization_id" in request:
        org_id = request["organization_id"]
        if org_id:
            org = org_cache.get_by_id(org_id)
            if not org:
                org = db.query(Organization).filter(Organization.id == org_id).first()
                if not org:
                    error_msg = Messages.error("organization_not_found", lang, org_id)
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
            user.organization_id = org_id

    # Write to database FIRST
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to update user ID %s in database: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        ) from e

    # Invalidate old cache entries
    try:
        user_cache.invalidate(user_id, old_phone)
        logger.debug("[Auth] Invalidated old cache for user ID %s", user_id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate cache for user ID %s: %s", user_id, e)

    # Re-cache updated user
    try:
        user_cache.cache_user(user)
        logger.info("[Auth] Updated and re-cached user ID %s", user_id)
    except Exception as e:
        logger.warning("[Auth] Failed to re-cache user ID %s: %s", user_id, e)

    # If organization changed, invalidate org cache
    if old_org_id != user.organization_id:
        try:
            if user.organization_id:
                new_org = org_cache.get_by_id(user.organization_id)
                if new_org:
                    org_cache.invalidate(user.organization_id, new_org.code, new_org.invitation_code)
            if old_org_id:
                old_org = org_cache.get_by_id(old_org_id)
                if old_org:
                    org_cache.invalidate(old_org_id, old_org.code, old_org.invitation_code)
        except Exception as e:
            logger.warning("[Auth] Failed to invalidate org cache: %s", e)

    # Get updated organization info
    org = org_cache.get_by_id(user.organization_id) if user.organization_id else None
    if not org and user.organization_id:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    logger.info("Admin %s updated user: %s", current_user.phone, user.phone)

    return {
        "message": Messages.success("user_updated", lang),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None
        }
    }


@router.delete("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Delete user (ADMIN ONLY)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Prevent deleting self
    if user.id == current_user.id:
        error_msg = Messages.error("cannot_delete_own_account", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    user_phone = user.phone

    # Delete from database FIRST
    db.delete(user)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to delete user ID %s in database: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        ) from e

    # Invalidate cache (non-blocking)
    try:
        user_cache.invalidate(user_id, user_phone)
        logger.info("[Auth] Invalidated cache for deleted user ID %s", user_id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate cache for deleted user ID %s: %s", user_id, e)

    logger.warning("Admin %s deleted user: %s", current_user.phone, user_phone)
    return {"message": Messages.success("user_deleted", lang, user_phone)}


@router.put("/admin/users/{user_id}/unlock", dependencies=[Depends(require_admin)])
async def unlock_user_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Unlock user account (ADMIN ONLY)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user.failed_login_attempts = 0
    user.locked_until = None

    # Write to database FIRST
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to unlock user ID %s in database: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlock user"
        ) from e

    # Invalidate and re-cache user
    try:
        user_cache.invalidate(user.id, user.phone)
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
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Prevent admin from resetting their own password
    if user.id == current_user.id:
        error_msg = Messages.error("cannot_reset_own_password", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Get password from request body, default to '12345678' if not provided
    password = request.get("password") if request and isinstance(request, dict) else None
    new_password = password if password and password.strip() else "12345678"

    # Validate password length
    if not new_password or len(new_password.strip()) == 0:
        error_msg = Messages.error("password_cannot_be_empty", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    if len(new_password.strip()) < 8:
        error_msg = Messages.error("password_too_short", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Reset password
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    # Write to database FIRST
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to reset password in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        ) from e

    # Invalidate and re-cache user
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
        logger.info("[Auth] Admin password reset and cache updated for user ID %s", user.id)
    except Exception as e:
        logger.warning("[Auth] Failed to update cache after admin password reset: %s", e)

    logger.info("Admin %s reset password for user: %s", current_user.phone, user.phone)
    return {"message": Messages.success("password_reset_for_user", lang, user.phone)}
