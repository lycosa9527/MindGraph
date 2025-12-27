"""
Admin Organization Management Endpoints
=======================================

Admin-only organization CRUD endpoints:
- GET /admin/organizations - List all organizations
- POST /admin/organizations - Create organization
- PUT /admin/organizations/{org_id} - Update organization
- DELETE /admin/organizations/{org_id} - Delete organization

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import Organization, User
from models.messages import Messages
from services.redis_org_cache import org_cache
from utils.invitations import normalize_or_generate

from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/organizations", dependencies=[Depends(require_admin)])
async def list_organizations_admin(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """List all organizations (ADMIN ONLY)"""
    orgs = db.query(Organization).all()
    result = []
    
    # Performance optimization: Get user counts for all organizations in one GROUP BY query
    user_counts_by_org = {}
    user_counts_query = db.query(
        User.organization_id,
        func.count(User.id).label('user_count')
    ).filter(
        User.organization_id.isnot(None)
    ).group_by(
        User.organization_id
    ).all()
    
    for count_result in user_counts_query:
        user_counts_by_org[count_result.organization_id] = count_result.user_count
    
    # Get token stats for all organizations (all-time totals)
    token_stats_by_org = {}
    
    try:
        from models.token_usage import TokenUsage
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
                TokenUsage.success == True
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
    except (ImportError, Exception) as e:
        logger.debug(f"TokenUsage not available yet: {e}")
    
    for org in orgs:
        user_count = user_counts_by_org.get(org.id, 0)
        org_token_stats = token_stats_by_org.get(org.id, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        })
        
        result.append({
            "id": org.id,
            "code": org.code,
            "name": org.name,
            "invitation_code": org.invitation_code,
            "user_count": user_count,
            "expires_at": utc_to_beijing_iso(org.expires_at),
            "is_active": org.is_active if hasattr(org, 'is_active') else True,
            "created_at": utc_to_beijing_iso(org.created_at),
            "token_stats": org_token_stats
        })
    return result


@router.post("/admin/organizations", dependencies=[Depends(require_admin)])
async def create_organization_admin(
    request: dict,
    http_request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """Create new organization (ADMIN ONLY)"""
    if not all(k in request for k in ["code", "name"]):
        error_msg = Messages.error("missing_required_fields", lang, "code, name")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    # Check code uniqueness (use cache with SQLite fallback)
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
    
    # Write to SQLite FIRST
    db.add(new_org)
    try:
        db.commit()
        db.refresh(new_org)
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] Failed to create org in SQLite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization"
        )
    
    # Write to Redis cache SECOND (non-blocking)
    try:
        org_cache.cache_org(new_org)
        logger.info(f"[Auth] New org cached: ID {new_org.id}, code {new_org.code}")
    except Exception as e:
        logger.warning(f"[Auth] Failed to cache new org ID {new_org.id}: {e}")
    
    logger.info(f"Admin {current_user.phone} created organization: {new_org.code}")
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
    http_request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """Update organization (ADMIN ONLY)"""
    # Load org (use cache with SQLite fallback)
    org = org_cache.get_by_id(org_id)
    if not org:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            error_msg = Messages.error("organization_not_found", lang, org_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    # Save old values for cache invalidation
    old_code = org.code
    old_invite = org.invitation_code
    
    # Update code (if provided)
    if "code" in request:
        new_code = (request["code"] or "").strip()
        if not new_code:
            error_msg = Messages.error("organization_code_empty", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_code) > 50:
            error_msg = Messages.error("organization_code_too_long", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if new_code != org.code:
            # Check code uniqueness (use cache)
            conflict = org_cache.get_by_code(new_code)
            if not conflict or conflict.id == org.id:
                conflict = db.query(Organization).filter(Organization.code == new_code).first()
            if conflict and conflict.id != org.id:
                error_msg = Messages.error("organization_exists", lang, new_code)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
            org.code = new_code

    if "name" in request:
        org.name = request["name"]
    if "invitation_code" in request:
        proposed = request.get("invitation_code")
        normalized = normalize_or_generate(
            proposed,
            request.get("name", org.name),
            request.get("code", org.code)
        )
        # Ensure uniqueness across organizations (exclude current org)
        conflict = org_cache.get_by_invitation_code(normalized)
        if conflict and conflict.id == org.id:
            conflict = None
        if not conflict:
            conflict = db.query(Organization).filter(
                Organization.invitation_code == normalized,
                Organization.id != org.id
            ).first()
        if conflict:
            attempts = 0
            while attempts < 5:
                normalized = normalize_or_generate(None, request.get("name", org.name), request.get("code", org.code))
                conflict = org_cache.get_by_invitation_code(normalized)
                if conflict and conflict.id == org.id:
                    conflict = None
                if not conflict:
                    conflict = db.query(Organization).filter(Organization.invitation_code == normalized, Organization.id != org.id).first()
                if not conflict:
                    break
                attempts += 1
            if attempts == 5:
                error_msg = Messages.error("failed_generate_invitation_code", lang)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
        org.invitation_code = normalized
    
    # Update expiration date (if provided)
    if "expires_at" in request:
        expires_str = request.get("expires_at")
        if expires_str:
            try:
                org.expires_at = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
            except ValueError:
                error_msg = Messages.error("invalid_date_format", lang)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        else:
            org.expires_at = None
    
    # Update active status (if provided)
    if "is_active" in request:
        org.is_active = bool(request.get("is_active"))
    
    # Write to SQLite FIRST
    try:
        db.commit()
        db.refresh(org)
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] Failed to update org ID {org_id} in SQLite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization"
        )
    
    # Invalidate old cache entries
    try:
        org_cache.invalidate(org_id, old_code, old_invite)
        logger.debug(f"[Auth] Invalidated old cache for org ID {org_id}")
    except Exception as e:
        logger.warning(f"[Auth] Failed to invalidate org cache: {e}")
    
    # Re-cache updated org
    try:
        org_cache.cache_org(org)
        logger.info(f"[Auth] Updated and re-cached org ID {org_id}")
    except Exception as e:
        logger.warning(f"[Auth] Failed to re-cache org ID {org_id}: {e}")
    
    logger.info(f"Admin {current_user.phone} updated organization: {org.code}")
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "invitation_code": org.invitation_code,
        "expires_at": org.expires_at.isoformat() if org.expires_at else None,
        "is_active": org.is_active if hasattr(org, 'is_active') else True,
        "created_at": org.created_at.isoformat() if org.created_at else None
    }


@router.delete("/admin/organizations/{org_id}", dependencies=[Depends(require_admin)])
async def delete_organization_admin(
    org_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language_dependency)
):
    """Delete organization (ADMIN ONLY)"""
    # Load org (use cache with SQLite fallback)
    org = org_cache.get_by_id(org_id)
    if not org:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            error_msg = Messages.error("organization_not_found", lang, org_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    # Save values for cache invalidation
    org_code = org.code
    org_invite = org.invitation_code
    
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    if user_count > 0:
        error_msg = Messages.error("cannot_delete_organization_with_users", lang, user_count)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    # Delete from SQLite FIRST
    db.delete(org)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] Failed to delete org ID {org_id} in SQLite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete organization"
        )
    
    # Invalidate cache (non-blocking)
    try:
        org_cache.invalidate(org_id, org_code, org_invite)
        logger.info(f"[Auth] Invalidated cache for deleted org ID {org_id}")
    except Exception as e:
        logger.warning(f"[Auth] Failed to invalidate cache for deleted org ID {org_id}: {e}")
    
    logger.warning(f"Admin {current_user.phone} deleted organization: {org.code}")
    return {"message": Messages.success("organization_deleted", lang, org.code)}

