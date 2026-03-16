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
from datetime import datetime, timezone
import logging
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from config.database import get_db
from models.domain.auth import Organization, User
from models.domain.messages import Messages, Language
try:
    from models.domain.token_usage import TokenUsage
except ImportError:
    TokenUsage = None
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from utils.invitations import generate_invitation_code, normalize_or_generate
from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso
from .stats import _sql_count

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/organizations", dependencies=[Depends(require_admin)])
async def list_organizations_admin(
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _lang: Language = Depends(get_language_dependency)
):
    """List all organizations (ADMIN ONLY)"""
    orgs = db.query(Organization).all()
    result = []

    # Performance optimization: Get user counts for all organizations in one GROUP BY query
    user_counts_by_org = {}
    user_counts_query = db.query(
        User.organization_id,
        _sql_count(User.id).label('user_count')
    ).filter(
        User.organization_id.isnot(None)
    ).group_by(
        User.organization_id
    ).all()

    for count_result in user_counts_query:
        user_counts_by_org[count_result.organization_id] = count_result.user_count

    # Get manager counts for all organizations
    manager_counts_by_org = {}
    manager_counts_query = db.query(
        User.organization_id,
        _sql_count(User.id).label('manager_count')
    ).filter(
        User.organization_id.isnot(None),
        User.role == 'manager'
    ).group_by(
        User.organization_id
    ).all()

    for count_result in manager_counts_query:
        manager_counts_by_org[count_result.organization_id] = count_result.manager_count

    # Get token stats for all organizations (all-time totals)
    token_stats_by_org = {}

    if TokenUsage is not None:
        try:
            org_token_stats = db.query(
                Organization.id,
                Organization.name,
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens'),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens')
            ).outerjoin(
                TokenUsage,
                and_(
                    Organization.id == TokenUsage.organization_id,
                    TokenUsage.success
                )
            ).group_by(
                Organization.id,
                Organization.name
            ).all()

            for org_stat in org_token_stats:
                token_stats_by_org[org_stat.id] = {
                    "input_tokens": int(org_stat.input_tokens or 0),
                    "output_tokens": int(org_stat.output_tokens or 0),
                    "total_tokens": int(org_stat.total_tokens or 0)
                }
        except Exception as e:
            logger.debug("TokenUsage query failed: %s", e)

    for org in orgs:
        user_count = user_counts_by_org.get(org.id, 0)
        manager_count = manager_counts_by_org.get(org.id, 0)
        org_token_stats = token_stats_by_org.get(org.id, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        })

        expires_at_val = cast(Optional[datetime], org.expires_at)
        created_at_val = cast(Optional[datetime], org.created_at)
        result.append({
            "id": org.id,
            "code": org.code,
            "name": org.name,
            "display_name": getattr(org, "display_name", None),
            "invitation_code": org.invitation_code,
            "user_count": user_count,
            "manager_count": manager_count,
            "expires_at": utc_to_beijing_iso(expires_at_val),
            "is_active": org.is_active if hasattr(org, 'is_active') else True,
            "created_at": utc_to_beijing_iso(created_at_val),
            "token_stats": org_token_stats
        })
    return result


@router.post("/admin/organizations", dependencies=[Depends(require_admin)])
async def create_organization_admin(
    request: dict,
    _http_request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Create new organization (ADMIN ONLY)"""
    if not all(k in request for k in ["code", "name"]):
        error_msg = Messages.error("missing_required_fields", lang, "code, name")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Check code uniqueness (use cache with database fallback)
    existing = org_cache.get_by_code(request["code"])
    if not existing:
        existing = db.query(Organization).filter(Organization.code == request["code"]).first()
    if existing:
        error_msg = Messages.error("organization_exists", lang, request["code"])
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)

    # Prepare invitation code: accept provided if valid, otherwise auto-generate
    provided_invite = request.get("invitation_code")
    invitation_code = normalize_or_generate(provided_invite, request.get("name"), request.get("code"))

    # Ensure uniqueness of invitation codes across organizations
    existing_invite = org_cache.get_by_invitation_code(invitation_code)
    if not existing_invite:
        existing_invite = db.query(Organization).filter(Organization.invitation_code == invitation_code).first()
    if existing_invite:
        attempts = 0
        while attempts < 5:
            invitation_code = normalize_or_generate(None, request.get("name"), request.get("code"))
            existing_invite = org_cache.get_by_invitation_code(invitation_code)
            if not existing_invite:
                existing_invite = db.query(Organization).filter(Organization.invitation_code == invitation_code).first()
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
        created_at=datetime.now(timezone.utc)
    )

    # Write to database FIRST
    db.add(new_org)
    try:
        db.commit()
        db.refresh(new_org)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to create org in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization"
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
        "created_at": new_org.created_at.isoformat()
    }


@router.put("/admin/organizations/{org_id}", dependencies=[Depends(require_admin)])
async def update_organization_admin(
    org_id: int,
    request: dict,
    _http_request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Update organization (ADMIN ONLY)"""
    # Load org from database (must be session-attached for commit/refresh)
    org = db.query(Organization).filter(Organization.id == org_id).first()
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
            conflict = org_cache.get_by_code(new_code)
            if conflict is None or int(conflict.id) == int(org.id):
                conflict = db.query(Organization).filter(Organization.code == new_code).first()
            if conflict is not None and int(conflict.id) != int(org.id):
                error_msg = Messages.error("organization_exists", lang, new_code)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
            setattr(org, 'code', new_code)

    if "name" in request:
        setattr(org, 'name', request["name"])
    if "display_name" in request:
        val = request.get("display_name")
        stripped = (val or "").strip() if val is not None else None
        setattr(org, 'display_name', stripped if stripped else None)
    if "invitation_code" in request:
        proposed = request.get("invitation_code")
        org_name_val = cast(Optional[str], org.name)
        org_code_val = cast(Optional[str], org.code)
        normalized = normalize_or_generate(
            proposed,
            request.get("name", org_name_val),
            request.get("code", org_code_val)
        )
        # Ensure uniqueness across organizations (exclude current org)
        conflict = org_cache.get_by_invitation_code(normalized)
        if conflict is not None and int(conflict.id) == int(org.id):
            conflict = None
        if conflict is None:
            conflict = db.query(Organization).filter(
                Organization.invitation_code == normalized,
                Organization.id != org.id
            ).first()
        if conflict is not None:
            attempts = 0
            while attempts < 5:
                normalized = normalize_or_generate(
                    None, request.get("name", org_name_val), request.get("code", org_code_val)
                )
                conflict = org_cache.get_by_invitation_code(normalized)
                if conflict is not None and int(conflict.id) == int(org.id):
                    conflict = None
                if conflict is None:
                    conflict = db.query(Organization).filter(
                        Organization.invitation_code == normalized,
                        Organization.id != org.id
                    ).first()
                if conflict is None:
                    break
                attempts += 1
            if attempts == 5:
                error_msg = Messages.error("failed_generate_invitation_code", lang)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
        setattr(org, 'invitation_code', normalized)

    # Update expiration date (if provided)
    if "expires_at" in request:
        expires_str = request.get("expires_at")
        if expires_str:
            try:
                setattr(org, 'expires_at', datetime.fromisoformat(expires_str.replace('Z', '+00:00')))
            except ValueError as exc:
                error_msg = Messages.error("invalid_date_format", lang)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg) from exc
        else:
            setattr(org, 'expires_at', None)

    # Update active status (if provided)
    if "is_active" in request:
        setattr(org, 'is_active', bool(request.get("is_active")))

    # Write to database FIRST
    try:
        db.commit()
        db.refresh(org)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to update org ID %s in database: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization"
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
        "is_active": org.is_active if hasattr(org, 'is_active') else True,
        "created_at": updated_created.isoformat() if updated_created else None
    }


@router.post("/admin/organizations/{org_id}/refresh-invitation-code", dependencies=[Depends(require_admin)])
async def refresh_organization_invitation_code(
    org_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Generate a new invitation code for the organization (ADMIN ONLY)"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        error_msg = Messages.error("organization_not_found", org_id, lang=lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    old_invite = cast(Optional[str], org.invitation_code)
    org_name_val = cast(Optional[str], org.name)
    org_code_val = cast(Optional[str], org.code)
    new_code = generate_invitation_code(org_name_val, org_code_val)

    def _has_conflict(code: str) -> bool:
        cached = org_cache.get_by_invitation_code(code)
        if cached is not None and int(cached.id) != int(org.id):
            return True
        if cached is None:
            other = db.query(Organization).filter(
                Organization.invitation_code == code,
                Organization.id != org.id
            ).first()
            return other is not None
        return False

    attempts = 0
    while _has_conflict(new_code) and attempts < 5:
        new_code = generate_invitation_code(org_name_val, org_code_val)
        attempts += 1
    if _has_conflict(new_code):
        error_msg = Messages.error("failed_generate_invitation_code", lang)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

    setattr(org, 'invitation_code', new_code)
    try:
        db.commit()
        db.refresh(org)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to refresh invitation code for org %s: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh invitation code"
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
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """Delete organization (ADMIN ONLY)"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    org_code = cast(Optional[str], org.code)
    org_invite = cast(Optional[str], org.invitation_code)

    user_count = db.query(User).filter(User.organization_id == org_id).count()
    if user_count > 0:
        error_msg = Messages.error("cannot_delete_organization_with_users", lang, user_count)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    db.delete(org)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to delete org ID %s in database: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete organization"
        ) from e

    # Invalidate cache (non-blocking)
    try:
        org_cache.invalidate(org_id, org_code, org_invite)
        logger.info("[Auth] Invalidated cache for deleted org ID %s", org_id)
    except Exception as e:
        logger.warning("[Auth] Failed to invalidate cache for deleted org ID %s: %s", org_id, e)

    logger.warning("Admin %s deleted organization: %s", current_user.phone, org_code)
    return {"message": Messages.success("organization_deleted", lang, org_code)}


# =============================================================================
# Organization Manager Endpoints
# =============================================================================

@router.get("/admin/organizations/{org_id}/users", dependencies=[Depends(require_admin)])
async def list_organization_users(
    org_id: int,
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    List all users in an organization (ADMIN ONLY)

    Used for manager selection dropdown in admin panel.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Get all users in this organization
    users = db.query(User).filter(User.organization_id == org_id).order_by(User.name).all()

    result = []
    for user in users:
        # Get role (default to 'user' if not set)
        role = getattr(user, 'role', 'user') or 'user'
        result.append({
            "id": user.id,
            "phone": user.phone[:3] + "****" + user.phone[-4:] if len(user.phone) == 11 else user.phone,
            "name": user.name or user.phone,
            "role": role,
            "is_manager": role == 'manager'
        })

    return {
        "organization": {
            "id": org.id,
            "code": org.code,
            "name": org.name
        },
        "users": result
    }


@router.get("/admin/organizations/{org_id}/managers", dependencies=[Depends(require_admin)])
async def list_organization_managers(
    org_id: int,
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    List managers of an organization (ADMIN ONLY)
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Get managers in this organization
    managers = db.query(User).filter(
        User.organization_id == org_id,
        User.role == 'manager'
    ).order_by(User.name).all()

    result = []
    for user in managers:
        result.append({
            "id": user.id,
            "phone": user.phone[:3] + "****" + user.phone[-4:] if len(user.phone) == 11 else user.phone,
            "name": user.name or user.phone
        })

    return {
        "organization": {
            "id": org.id,
            "code": org.code,
            "name": org.name
        },
        "managers": result
    }


@router.put("/admin/organizations/{org_id}/managers/{user_id}", dependencies=[Depends(require_admin)])
async def set_organization_manager(
    org_id: int,
    user_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Set a user as manager of their organization (ADMIN ONLY)

    The user must belong to the specified organization.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Verify user belongs to this organization
    if user.organization_id != org_id:
        error_msg = Messages.error("user_not_in_organization", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Set role to manager
    user.role = 'manager'

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to set manager role for user ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set manager role"
        ) from e

    # Invalidate user cache
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
    except Exception as e:
        logger.warning("[Auth] Failed to update user cache: %s", e)

    logger.info("Admin %s set user %s as manager of org %s", current_user.phone, user.phone, org.code)

    return {
        "message": Messages.success("manager_role_set", lang, user.name or user.phone),
        "user": {
            "id": user.id,
            "name": user.name,
            "role": user.role
        }
    }


@router.delete("/admin/organizations/{org_id}/managers/{user_id}", dependencies=[Depends(require_admin)])
async def remove_organization_manager(
    org_id: int,
    user_id: int,
    _request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: Language = Depends(get_language_dependency)
):
    """
    Remove manager role from a user (ADMIN ONLY)

    Resets the user's role back to 'user'.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    # Verify user belongs to this organization
    if user.organization_id != org_id:
        error_msg = Messages.error("user_not_in_organization", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Reset role to user
    user.role = 'user'

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error("[Auth] Failed to remove manager role from user ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove manager role"
        ) from e

    # Invalidate user cache
    try:
        user_cache.invalidate(user.id, user.phone)
        user_cache.cache_user(user)
    except Exception as e:
        logger.warning("[Auth] Failed to update user cache: %s", e)

    logger.info("Admin %s removed manager role from user %s in org %s", current_user.phone, user.phone, org.code)

    return {
        "message": Messages.success("manager_role_removed", lang, user.name or user.phone),
        "user": {
            "id": user.id,
            "name": user.name,
            "role": user.role
        }
    }
