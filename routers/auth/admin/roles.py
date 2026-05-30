"""Admin Role Control Endpoints.

Admin-only endpoints for listing admins and granting/revoking admin access:
- GET /admin/admins - List all users with superadmin role (database)
- PUT /admin/users/{user_id}/role - Update user role (grant/revoke platform roles)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Messages, Language
from services.redis.cache.redis_user_cache import user_cache
from utils.auth.config import ADMIN_PHONES, ADMIN_USER_IDS
from utils.auth.role_constants import (
    ROLE_SCHOOL_ADMIN,
    ROLE_SUPERADMIN,
    SUPERADMIN_ROLES,
    VALID_ASSIGNABLE_ROLES,
    normalize_role,
)
from utils.auth.school_tier import assert_organization_has_manager_capacity

from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso


logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ROLES = VALID_ASSIGNABLE_ROLES


def _admin_env_phone_or_clause(env_tokens: list[str]):
    """SQL OR for exact phone match or case-insensitive UUID phone match."""
    clauses = []
    seen_lower_uuid: set[str] = set()
    for raw in env_tokens:
        token = raw.strip()
        if not token:
            continue
        clauses.append(User.phone == token)
        try:
            lower_uuid = str(uuid.UUID(token)).lower()
            if lower_uuid not in seen_lower_uuid:
                seen_lower_uuid.add(lower_uuid)
                clauses.append(func.lower(User.phone) == lower_uuid)
        except ValueError:
            pass
    if not clauses:
        return None
    return or_(*clauses)


def _user_for_admin_env_token(user_pool: dict[int, User], token: str) -> User | None:
    """Resolve env ADMIN_PHONES token to a user from a pre-fetched pool."""
    t = token.strip()
    if not t:
        return None
    try:
        want_u = str(uuid.UUID(t)).lower()
    except ValueError:
        want_u = None
    for u in user_pool.values():
        if not u.phone:
            continue
        if u.phone.strip() == t:
            return u
        if want_u:
            try:
                if str(uuid.UUID(u.phone.strip())).lower() == want_u:
                    return u
            except ValueError:
                continue
    return None


@router.get("/admin/admins", dependencies=[Depends(require_admin)])
async def list_admins(
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all users with superadmin role in database (ADMIN ONLY).

    Returns users where role is superadmin (or legacy admin), plus env-configured
    ADMIN_PHONES and ADMIN_USER_IDS as read-only reference.
    """
    admin_stmt = (
        select(User)
        .where(User.role.in_(tuple(SUPERADMIN_ROLES)))
        .order_by(User.created_at.asc())
    )
    admin_users = (await db.execute(admin_stmt)).scalars().all()

    db_admin_ids = {u.id for u in admin_users}
    env_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]

    env_admins = []
    env_user_pool: dict[int, User] = {}
    phone_clause = _admin_env_phone_or_clause(env_phones)
    if phone_clause is not None:
        env_phone_stmt = select(User).where(phone_clause)
        for u in (await db.execute(env_phone_stmt)).scalars().all():
            env_user_pool[u.id] = u
    if ADMIN_USER_IDS:
        env_id_stmt = select(User).where(User.id.in_(ADMIN_USER_IDS))
        for u in (await db.execute(env_id_stmt)).scalars().all():
            env_user_pool[u.id] = u

    for phone in env_phones:
        user = _user_for_admin_env_token(env_user_pool, phone)
        if user is not None and user.id in db_admin_ids:
            continue
        env_admins.append(
            {
                "phone": phone,
                "user_id": user.id if user else None,
                "name": user.name if user else None,
            }
        )

    for uid in sorted(ADMIN_USER_IDS):
        if uid in db_admin_ids:
            continue
        if any(row.get("user_id") == uid for row in env_admins):
            continue
        user = env_user_pool.get(uid)
        display_phone = user.phone.strip() if user and user.phone else f"user_id:{uid}"
        env_admins.append(
            {
                "phone": display_phone,
                "user_id": uid,
                "name": user.name if user else None,
            }
        )

    result = []
    for user in admin_users:
        phone = user.phone or getattr(user, "email", None) or ""
        masked_phone = phone[:3] + "****" + phone[-4:] if user.phone and len(user.phone) == 11 else phone

        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": user.name,
                "role": normalize_role(user.role),
                "source": "database",
                "created_at": utc_to_beijing_iso(user.created_at),
            }
        )

    return {
        "admins": result,
        "env_admins": env_admins,
        "env_admins_note": (
            "Configured via ADMIN_PHONES and ADMIN_USER_IDS environment variables (read-only)"
        ),
    }


@router.put("/admin/users/{user_id}/role", dependencies=[Depends(require_admin)])
async def update_user_role(
    user_id: int,
    role: str = Query(..., description="New canonical role slug"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Update user role (SUPERADMIN ONLY).

    Valid roles: all seven canonical slugs (superadmin, platform_bd, expert,
    school_admin, teacher, personal_trial, personal_paid).
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

    old_role = normalize_role(user.role)

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

    if old_role == ROLE_SUPERADMIN and role != ROLE_SUPERADMIN:
        count_stmt = (
            select(sa_count())
            .select_from(User)
            .where(User.role.in_(tuple(SUPERADMIN_ROLES)))
        )
        admin_count = (await db.execute(count_stmt)).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("cannot_remove_last_admin", lang=lang),
            )

    if role == ROLE_SCHOOL_ADMIN and old_role != ROLE_SCHOOL_ADMIN:
        org_id = getattr(user, "organization_id", None)
        if org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("user_not_in_organization", lang),
            )
        org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
        if org is None:
            error_msg = Messages.error("organization_not_found", lang, org_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        await assert_organization_has_manager_capacity(db, org, lang)

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

    if role == ROLE_SUPERADMIN:
        logger.info("Superadmin %s granted superadmin role to user %s", current_user.phone, user.phone)
    elif old_role == ROLE_SUPERADMIN:
        logger.info("Superadmin %s revoked superadmin role from user %s", current_user.phone, user.phone)
    else:
        logger.info(
            "Superadmin %s changed role for user %s from %s to %s",
            current_user.phone,
            user.phone,
            old_role,
            role,
        )

    granted_superadmin = role == ROLE_SUPERADMIN
    return {
        "message": Messages.success(
            "admin_role_granted" if granted_superadmin else "admin_role_revoked",
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
