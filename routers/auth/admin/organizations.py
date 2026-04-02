"""Admin Organization Management Endpoints.

Admin-only organization CRUD endpoints:
- GET /admin/organizations - List all organizations
- POST /admin/organizations - Create organization
- PUT /admin/organizations/{org_id} - Update organization
- DELETE /admin/organizations/{org_id} - Delete organization

Write-through pattern (PostgreSQL + Redis):
- Database is source of truth; always load org from db Session for writes (update/delete).
- Write order: 1) db.commit(), 2) invalidate old cache keys, 3) cache_org(updated).
- Cache used only for read-only lookups (existence, conflict checks).
- Detached org from Redis cache must never be passed to db.commit/delete/refresh.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
import logging
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce as sa_coalesce, count as sa_count, sum as sa_sum

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.diagrams import Diagram
from models.domain.messages import Messages, Language
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_usage_stats import UserUsageStats

try:
    from models.domain.token_usage import TokenUsage
except ImportError:
    TokenUsage = None
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from utils.invitations import generate_invitation_code, normalize_or_generate
from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/organizations", dependencies=[Depends(require_admin)])
async def list_organizations_admin(
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    _lang: Language = Depends(get_language_dependency),
):
    """List all organizations (ADMIN ONLY)"""
    orgs = (await db.execute(select(Organization))).scalars().all()
    result = []

    user_counts_by_org = {}
    user_counts_stmt = (
        select(User.organization_id, sa_count(User.id).label("user_count"))
        .where(User.organization_id.isnot(None))
        .group_by(User.organization_id)
    )
    user_counts_query = (await db.execute(user_counts_stmt)).all()

    for count_result in user_counts_query:
        user_counts_by_org[count_result.organization_id] = count_result.user_count

    manager_counts_by_org = {}
    manager_counts_stmt = (
        select(User.organization_id, sa_count(User.id).label("manager_count"))
        .where(User.organization_id.isnot(None), User.role == "manager")
        .group_by(User.organization_id)
    )
    manager_counts_query = (await db.execute(manager_counts_stmt)).all()

    for count_result in manager_counts_query:
        manager_counts_by_org[count_result.organization_id] = count_result.manager_count

    token_stats_by_org = {}

    if TokenUsage is not None:
        try:
            org_token_stmt = (
                select(
                    Organization.id,
                    Organization.name,
                    sa_coalesce(sa_sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                    sa_coalesce(sa_sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                )
                .outerjoin(
                    TokenUsage,
                    and_(
                        Organization.id == TokenUsage.organization_id,
                        TokenUsage.success,
                    ),
                )
                .group_by(Organization.id, Organization.name)
            )
            org_token_stats = (await db.execute(org_token_stmt)).all()

            for org_stat in org_token_stats:
                token_stats_by_org[org_stat.id] = {
                    "input_tokens": int(org_stat.input_tokens or 0),
                    "output_tokens": int(org_stat.output_tokens or 0),
                    "total_tokens": int(org_stat.total_tokens or 0),
                }
        except Exception as e:
            logger.debug("TokenUsage query failed: %s", e)

    for org in orgs:
        user_count = user_counts_by_org.get(org.id, 0)
        manager_count = manager_counts_by_org.get(org.id, 0)
        org_token_stats = token_stats_by_org.get(org.id, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

        expires_at_val = cast(Optional[datetime], org.expires_at)
        created_at_val = cast(Optional[datetime], org.created_at)
        result.append(
            {
                "id": org.id,
                "code": org.code,
                "name": org.name,
                "display_name": getattr(org, "display_name", None),
                "invitation_code": org.invitation_code,
                "user_count": user_count,
                "manager_count": manager_count,
                "expires_at": utc_to_beijing_iso(expires_at_val),
                "is_active": org.is_active if hasattr(org, "is_active") else True,
                "created_at": utc_to_beijing_iso(created_at_val),
                "token_stats": org_token_stats,
            }
        )
    return result


@router.post("/admin/organizations", dependencies=[Depends(require_admin)])
async def create_organization_admin(
    request: dict,
    _http_request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Create new organization (ADMIN ONLY)"""
    if not all(k in request for k in ["code", "name"]):
        error_msg = Messages.error("missing_required_fields", lang, "code, name")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    existing = await org_cache.get_by_code(request["code"])
    if not existing:
        existing = (
            await db.execute(select(Organization).where(Organization.code == request["code"]))
        ).scalar_one_or_none()
    if existing:
        error_msg = Messages.error("organization_exists", lang, request["code"])
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)

    # Prepare invitation code: accept provided if valid, otherwise auto-generate
    provided_invite = request.get("invitation_code")
    invitation_code = normalize_or_generate(provided_invite, request.get("name"), request.get("code"))

    # Ensure uniqueness of invitation codes across organizations
    existing_invite = await org_cache.get_by_invitation_code(invitation_code)
    if not existing_invite:
        existing_invite = (
            await db.execute(select(Organization).where(Organization.invitation_code == invitation_code))
        ).scalar_one_or_none()
    if existing_invite:
        attempts = 0
        while attempts < 5:
            invitation_code = normalize_or_generate(None, request.get("name"), request.get("code"))
            existing_invite = await org_cache.get_by_invitation_code(invitation_code)
            if not existing_invite:
                existing_invite = (
                    await db.execute(select(Organization).where(Organization.invitation_code == invitation_code))
                ).scalar_one_or_none()
            if not existing_invite:
                break
            attempts += 1
        if attempts == 5:
            error_msg = Messages.error("failed_generate_invitation_code", lang)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)

    new_org = Organization(
        code=request["code"],
        name=request["name"],
        invitation_code=invitation_code,
        created_at=datetime.now(UTC),
    )

    db.add(new_org)
    try:
        await db.commit()
        await db.refresh(new_org)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to create org in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        ) from e

    # Write to Redis cache SECOND (non-blocking)
    try:
        org_cache.cache_org(new_org)
        logger.info("[Auth] New org cached: ID %s, code %s", new_org.id, new_org.code)
    except Exception as e:
        logger.warning("[Auth] Failed to cache new org ID %s: %s", new_org.id, e)

    logger.info("Admin %s created organization: %s", current_user.phone, new_org.code)
    return {
        "id": new_org.id,
        "code": new_org.code,
        "name": new_org.name,
        "invitation_code": new_org.invitation_code,
        "created_at": new_org.created_at.isoformat(),
    }


@router.put("/admin/organizations/{org_id}", dependencies=[Depends(require_admin)])
async def update_organization_admin(
    org_id: int,
    request: dict,
    _http_request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Update organization (ADMIN ONLY)"""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Save old values for cache invalidation
    old_code = cast(Optional[str], org.code)
    old_invite = cast(Optional[str], org.invitation_code)

    # Update code (if provided)
    if "code" in request:
        new_code = (request["code"] or "").strip()
        if not new_code:
            error_msg = Messages.error("organization_code_empty", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_code) > 50:
            error_msg = Messages.error("organization_code_too_long", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        org_code_val = cast(Optional[str], org.code)
        if new_code != org_code_val:
            # Check code uniqueness (use cache)
            conflict = await org_cache.get_by_code(new_code)
            if conflict is None or cast(int, conflict.id) == cast(int, org.id):
                conflict = (
                    await db.execute(select(Organization).where(Organization.code == new_code))
                ).scalar_one_or_none()
            if conflict is not None and cast(int, conflict.id) != cast(int, org.id):
                error_msg = Messages.error("organization_exists", lang, new_code)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
            setattr(org, "code", new_code)

    if "name" in request:
        setattr(org, "name", request["name"])
    if "display_name" in request:
        val = request.get("display_name")
        stripped = (val or "").strip() if val is not None else None
        setattr(org, "display_name", stripped if stripped else None)
    if "invitation_code" in request:
        proposed = request.get("invitation_code")
        org_name_val = cast(Optional[str], org.name)
        org_code_val = cast(Optional[str], org.code)
        normalized = normalize_or_generate(
            proposed,
            request.get("name", org_name_val),
            request.get("code", org_code_val),
        )
        # Ensure uniqueness across organizations (exclude current org)
        conflict = await org_cache.get_by_invitation_code(normalized)
        if conflict is not None and cast(int, conflict.id) == cast(int, org.id):
            conflict = None
        if conflict is None:
            conflict = (
                await db.execute(
                    select(Organization).where(
                        Organization.invitation_code == normalized,
                        Organization.id != org.id,
                    )
                )
            ).scalar_one_or_none()
        if conflict is not None:
            attempts = 0
            while attempts < 5:
                normalized = normalize_or_generate(
                    None,
                    request.get("name", org_name_val),
                    request.get("code", org_code_val),
                )
                conflict = await org_cache.get_by_invitation_code(normalized)
                if conflict is not None and cast(int, conflict.id) == cast(int, org.id):
                    conflict = None
                if conflict is None:
                    conflict = (
                        await db.execute(
                            select(Organization).where(
                                Organization.invitation_code == normalized,
                                Organization.id != org.id,
                            )
                        )
                    ).scalar_one_or_none()
                if conflict is None:
                    break
                attempts += 1
            if attempts == 5:
                error_msg = Messages.error("failed_generate_invitation_code", lang)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
        setattr(org, "invitation_code", normalized)

    # Update expiration date (if provided)
    if "expires_at" in request:
        expires_str = request.get("expires_at")
        if expires_str:
            try:
                setattr(
                    org,
                    "expires_at",
                    datetime.fromisoformat(expires_str.replace("Z", "+00:00")),
                )
            except ValueError as exc:
                error_msg = Messages.error("invalid_date_format", lang)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg) from exc
        else:
            setattr(org, "expires_at", None)

    # Update active status (if provided)
    if "is_active" in request:
        setattr(org, "is_active", bool(request.get("is_active")))

    try:
        await db.commit()
        await db.refresh(org)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to update org ID %s in database: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization",
        ) from e

    if not org_cache.write_through(org, old_code, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org_id)
    else:
        logger.info("[Auth] Updated and re-cached org ID %s", org_id)

    logger.info("Admin %s updated organization: %s", current_user.phone, org.code)
    updated_expires = cast(Optional[datetime], org.expires_at)
    updated_created = cast(Optional[datetime], org.created_at)
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "display_name": getattr(org, "display_name", None),
        "invitation_code": org.invitation_code,
        "expires_at": updated_expires.isoformat() if updated_expires else None,
        "is_active": org.is_active if hasattr(org, "is_active") else True,
        "created_at": updated_created.isoformat() if updated_created else None,
    }


@router.post(
    "/admin/organizations/{org_id}/refresh-invitation-code",
    dependencies=[Depends(require_admin)],
)
async def refresh_organization_invitation_code(
    org_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Generate a new invitation code for the organization (ADMIN ONLY)"""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        error_msg = Messages.error("organization_not_found", org_id, lang=lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    old_invite = cast(Optional[str], org.invitation_code)
    org_name_val = cast(Optional[str], org.name)
    org_code_val = cast(Optional[str], org.code)
    new_code = generate_invitation_code(org_name_val, org_code_val)

    async def _has_conflict(code: str) -> bool:
        cached = await org_cache.get_by_invitation_code(code)
        if cached is not None and cast(int, cached.id) != cast(int, org.id):
            return True
        if cached is None:
            other = (
                await db.execute(
                    select(Organization).where(
                        Organization.invitation_code == code,
                        Organization.id != org.id,
                    )
                )
            ).scalar_one_or_none()
            return other is not None
        return False

    attempts = 0
    while await _has_conflict(new_code) and attempts < 5:
        new_code = generate_invitation_code(org_name_val, org_code_val)
        attempts += 1
    if await _has_conflict(new_code):
        error_msg = Messages.error("failed_generate_invitation_code", lang)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)

    setattr(org, "invitation_code", new_code)
    try:
        await db.commit()
        await db.refresh(org)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to refresh invitation code for org %s: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh invitation code",
        ) from e

    if not org_cache.write_through(org, org_code_val, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org_id)

    logger.info("Admin %s refreshed invitation code for org %s", current_user.phone, org.code)
    return {
        "id": org.id,
        "invitation_code": org.invitation_code,
    }


@router.delete("/admin/organizations/{org_id}", dependencies=[Depends(require_admin)])
async def delete_organization_admin(
    org_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
    delete_users: bool = False,
):
    """Delete organization (ADMIN ONLY). Use delete_users=true to also remove all user accounts."""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    org_code = cast(Optional[str], org.code)
    org_invite = cast(Optional[str], org.invitation_code)

    users_stmt = select(User).where(User.organization_id == org_id)
    users_in_org = (await db.execute(users_stmt)).scalars().all()
    user_count = len(users_in_org)

    if user_count > 0 and not delete_users:
        error_msg = Messages.error("cannot_delete_organization_with_users", lang, user_count)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    if delete_users and user_count > 0:
        for user in users_in_org:
            uid = user.id
            await db.execute(delete(Diagram).where(Diagram.user_id == uid))
            await db.execute(delete(UserActivityLog).where(UserActivityLog.user_id == uid))
            await db.execute(delete(UserUsageStats).where(UserUsageStats.user_id == uid))
            if TokenUsage is not None:
                await db.execute(update(TokenUsage).where(TokenUsage.user_id == uid).values(user_id=None))
            user_cache.invalidate(uid, user.phone)
            await db.delete(user)
        try:
            await db.flush()
        except Exception as e:
            await db.rollback()
            logger.error("[Auth] Failed to delete users for org %s: %s", org_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete organization users",
            ) from e

    await db.delete(org)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to delete org ID %s in database: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete organization",
        ) from e

    try:
        org_cache.invalidate(org_id, org_code, org_invite)
        logger.info("[Auth] Invalidated cache for deleted org ID %s", org_id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate cache for deleted org ID %s: %s", org_id, e)

    logger.warning(
        "Admin %s deleted organization: %s (users: %s)",
        current_user.phone,
        org_code,
        user_count if delete_users else 0,
    )
    return {"message": Messages.success("organization_deleted", lang, org_code)}


# =============================================================================
# Organization Manager Endpoints
# =============================================================================


@router.get("/admin/managers", dependencies=[Depends(require_admin)])
async def list_all_managers(
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    _lang: Language = Depends(get_language_dependency),
):
    """
    List all managers across all organizations (ADMIN ONLY).

    Returns managers with their organization info for the role control panel.
    """
    managers_stmt = (
        select(User)
        .where(User.organization_id.isnot(None), User.role == "manager")
        .order_by(User.organization_id, User.name)
    )
    managers = (await db.execute(managers_stmt)).scalars().all()

    org_ids = list({u.organization_id for u in managers if u.organization_id})
    orgs_by_id: dict[int, Organization] = {}
    if org_ids:
        org_stmt = select(Organization).where(Organization.id.in_(org_ids))
        orgs = (await db.execute(org_stmt)).scalars().all()
        orgs_by_id = {cast(int, org.id): org for org in orgs}

    result = []
    for user in managers:
        org = orgs_by_id.get(user.organization_id) if user.organization_id else None
        masked_phone = user.phone
        if len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]
        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "phone_real": user.phone,
                "name": user.name or user.phone,
                "organization_id": user.organization_id,
                "organization_code": org.code if org else None,
                "organization_name": org.name if org else None,
                "created_at": utc_to_beijing_iso(user.created_at),
            }
        )

    return {"managers": result}


@router.get("/admin/organizations/{org_id}/users", dependencies=[Depends(require_admin)])
async def list_organization_users(
    org_id: int,
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    List all users in an organization (ADMIN ONLY)

    Used for manager selection dropdown in admin panel.
    """
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    users_stmt = select(User).where(User.organization_id == org_id).order_by(User.name)
    users = (await db.execute(users_stmt)).scalars().all()

    result = []
    for user in users:
        # Get role (default to 'user' if not set)
        role = getattr(user, "role", "user") or "user"
        result.append(
            {
                "id": user.id,
                "phone": user.phone[:3] + "****" + user.phone[-4:] if len(user.phone) == 11 else user.phone,
                "name": user.name or user.phone,
                "role": role,
                "is_manager": role == "manager",
            }
        )

    return {
        "organization": {"id": org.id, "code": org.code, "name": org.name},
        "users": result,
    }


@router.get("/admin/organizations/{org_id}/managers", dependencies=[Depends(require_admin)])
async def list_organization_managers(
    org_id: int,
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    List managers of an organization (ADMIN ONLY)
    """
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    managers_stmt = select(User).where(User.organization_id == org_id, User.role == "manager").order_by(User.name)
    managers = (await db.execute(managers_stmt)).scalars().all()

    result = []
    for user in managers:
        result.append(
            {
                "id": user.id,
                "phone": user.phone[:3] + "****" + user.phone[-4:] if len(user.phone) == 11 else user.phone,
                "name": user.name or user.phone,
            }
        )

    return {
        "organization": {"id": org.id, "code": org.code, "name": org.name},
        "managers": result,
    }


@router.put(
    "/admin/organizations/{org_id}/managers/{user_id}",
    dependencies=[Depends(require_admin)],
)
async def set_organization_manager(
    org_id: int,
    user_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Set a user as manager of their organization (ADMIN ONLY)

    The user must belong to the specified organization.
    """
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Verify user belongs to this organization
    if user.organization_id != org_id:
        error_msg = Messages.error("user_not_in_organization", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Set role to manager
    user.role = "manager"

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to set manager role for user ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set manager role",
        ) from e

    # Invalidate user cache
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
    except Exception as e:
        logger.warning("[Auth] Failed to update user cache: %s", e)

    logger.info(
        "Admin %s set user %s as manager of org %s",
        current_user.phone,
        user.phone,
        org.code,
    )

    return {
        "message": Messages.success("manager_role_set", lang, user.name or user.phone),
        "user": {"id": user.id, "name": user.name, "role": user.role},
    }


@router.delete(
    "/admin/organizations/{org_id}/managers/{user_id}",
    dependencies=[Depends(require_admin)],
)
async def remove_organization_manager(
    org_id: int,
    user_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Remove manager role from a user (ADMIN ONLY)

    Resets the user's role back to 'user'.
    """
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Verify user belongs to this organization
    if user.organization_id != org_id:
        error_msg = Messages.error("user_not_in_organization", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Reset role to user
    user.role = "user"

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to remove manager role from user ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove manager role",
        ) from e

    # Invalidate user cache
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
    except Exception as e:
        logger.warning("[Auth] Failed to update user cache: %s", e)

    logger.info(
        "Admin %s removed manager role from user %s in org %s",
        current_user.phone,
        user.phone,
        org.code,
    )

    return {
        "message": Messages.success("manager_role_removed", lang, user.name or user.phone),
        "user": {"id": user.id, "name": user.name, "role": user.role},
    }
