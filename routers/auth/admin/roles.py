"""Admin Role Control Endpoints.

Admin-only endpoints for listing admins and granting/revoking admin access:
- GET /admin/admins - List all users with admin role (database)
- PUT /admin/users/{user_id}/role - Update user role (grant/revoke admin)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Messages, Language
from services.redis.cache.redis_user_cache import user_cache
from utils.auth.config import ADMIN_PHONES

from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso


logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ROLES = frozenset({"user", "manager", "admin"})


@router.get("/admin/admins", dependencies=[Depends(require_admin)])
async def list_admins(
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all users with admin role in database (ADMIN ONLY).

    Returns users where role='admin', plus env-configured ADMIN_PHONES
    as read-only reference.
    """
    admin_stmt = select(User).where(User.role.in_(["admin", "superadmin"])).order_by(User.created_at.asc())
    admin_users = (await db.execute(admin_stmt)).scalars().all()

    admin_phones = {u.phone for u in admin_users}
    env_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]

    env_admins = []
    if env_phones:
        env_stmt = select(User).where(User.phone.in_(env_phones))
        env_users = (await db.execute(env_stmt)).scalars().all()
        user_by_phone = {u.phone: u for u in env_users}
        for phone in env_phones:
            if phone in admin_phones:
                continue
            user = user_by_phone.get(phone)
            env_admins.append(
                {
                    "phone": phone,
                    "name": user.name if user else None,
                }
            )

    result = []
    for user in admin_users:
        masked_phone = user.phone
        if len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]

        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": user.name,
                "role": user.role,
                "source": "database",
                "created_at": utc_to_beijing_iso(user.created_at),
            }
        )

    return {
        "admins": result,
        "env_admins": env_admins,
        "env_admins_note": "Configured via ADMIN_PHONES environment variable (read-only)",
    }


@router.put("/admin/users/{user_id}/role", dependencies=[Depends(require_admin)])
async def update_user_role(
    user_id: int,
    role: str = Query(..., description="New role: user, manager, or admin"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Update user role - grant or revoke admin access (ADMIN ONLY).

    Valid roles: user, manager, admin.
    - Grant admin: set role='admin'
    - Revoke admin: set role='user' (or 'manager')
    """
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_role", role, lang=lang),
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("user_not_found", user_id, lang=lang),
        )

    old_role = user.role or "user"

    if old_role == role:
        return {
            "message": Messages.success("user_updated", lang=lang),
            "user": {
                "id": user.id,
                "phone": user.phone,
                "name": user.name,
                "role": role,
            },
        }

    if old_role in ("admin", "superadmin") and role not in ("admin", "superadmin"):
        count_stmt = select(sa_count()).select_from(User).where(User.role.in_(["admin", "superadmin"]))
        admin_count = (await db.execute(count_stmt)).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("cannot_remove_last_admin", lang=lang),
            )

    user.role = role
    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to update user role ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role",
        ) from e

    try:
        await user_cache.invalidate(user_id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate/cache user %s: %s", user_id, e)

    if role == "admin":
        logger.info("Admin %s granted admin role to user %s", current_user.phone, user.phone)
    else:
        logger.info("Admin %s revoked admin role from user %s", current_user.phone, user.phone)

    return {
        "message": Messages.success(
            "admin_role_granted" if role == "admin" else "admin_role_revoked",
            user.phone,
            lang=lang,
        ),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "role": user.role,
        },
    }
