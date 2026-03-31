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
from sqlalchemy.orm import Session

from config.database import get_db
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
def list_admins(
    db: Session = Depends(get_db),
):
    """
    List all users with admin role in database (ADMIN ONLY).

    Returns users where role='admin', plus env-configured ADMIN_PHONES
    as read-only reference.
    """
    admin_users = db.query(User).filter(User.role.in_(["admin", "superadmin"])).order_by(User.created_at.asc()).all()

    env_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]

    env_admins = []
    if env_phones:
        env_users = db.query(User).filter(User.phone.in_(env_phones)).all()
        user_by_phone = {u.phone: u for u in env_users}
        for phone in env_phones:
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
                "phone_real": user.phone,
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
def update_user_role(
    user_id: int,
    role: str = Query(..., description="New role: user, manager, or admin"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
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

    user = db.query(User).filter(User.id == user_id).first()
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
        admin_count = db.query(User).filter(User.role.in_(["admin", "superadmin"])).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("cannot_remove_last_admin", lang=lang),
            )

    user.role = role
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to update user role ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role",
        ) from e

    try:
        user_cache.invalidate(user_id, user.phone)
        user_cache.cache_user(user)
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
