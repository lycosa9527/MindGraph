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

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce as sa_coalesce, count as sa_count, sum as sa_sum

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Messages, Language

try:
    from models.domain.token_usage import TokenUsage
except ImportError:
    TokenUsage = None
from services.auth.user_fk_cleanup import delete_user_fk_dependent_rows
from services.redis.cache.redis_org_cache import org_cache
from services.redis.cache.redis_user_cache import user_cache
from utils.auth.role_constants import ROLE_TEACHER, SCHOOL_ADMIN_ROLES, normalize_role
from utils.auth.roles import is_superadmin
from utils.auth.mindbot_token_stats import add_token_period, aggregate_mindbot_token_totals
from utils.auth.school_tier import (
    apply_extra_member_seats_on_update,
    apply_school_tier_on_create,
    apply_school_tier_on_update,
    assert_organization_has_manager_capacity,
    assert_organization_tier_allows_current_managers,
    assert_organization_tier_allows_current_members,
    clear_extra_member_seats_if_trial,
    manager_limit_for_org,
    member_count_for_org,
    school_tier_list_fields,
)
from utils.auth.admin_panel_permissions import CAP_TAB_INVITES_VIEW, CAP_TAB_ORGANIZATIONS_VIEW
from utils.auth.org_privatization import org_privatization_list_field
from utils.auth.admin_scope import (
    AdminScope,
    assert_panel_org_readable,
    assert_resource_org_in_scope,
    org_filter,
    panel_org_table_filter,
)
from utils.invitations import generate_invitation_code, normalize_or_generate
from utils.sensitive_mask import mask_invitation_code
from .organization_dify import (
    apply_dify_on_create,
    apply_dify_on_update,
    dify_list_fields,
    global_mindmate_dify_fields,
    propagate_org_dify_settings_to_mindbot_configs,
    probe_mindmate_dify_health,
    probe_mindmate_dify_health_draft,
)
from .organization_mindmate_branding import (
    apply_mindmate_branding_on_update,
    finalize_mindmate_avatar_upload,
    mindmate_branding_list_fields,
    purge_org_mindmate_avatar_storage,
    revert_mindmate_avatar_upload,
    save_mindmate_agent_avatar,
)

from ..dependencies import (
    get_admin_scope,
    get_language_dependency,
    require_global_organizations_edit,
    require_global_organizations_read,
    require_invite_org_create,
)
from ..helpers import utc_to_beijing_iso

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/organizations")
async def list_organizations_admin(
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_read),
    db: AsyncSession = Depends(get_async_db),
    _lang: Language = Depends(get_language_dependency),
):
    """List all organizations (ADMIN ONLY)"""
    orgs = (
        await db.execute(
            select(Organization)
            .where(panel_org_table_filter(scope))
            .order_by(Organization.id)
        )
    ).scalars().all()
    result = []

    user_counts_by_org = {}
    user_counts_stmt = (
        select(User.organization_id, sa_count(User.id).label("user_count"))
        .where(
            User.organization_id.isnot(None),
            org_filter(scope, User.organization_id),
        )
        .group_by(User.organization_id)
    )
    user_counts_query = (await db.execute(user_counts_stmt)).all()

    for count_result in user_counts_query:
        user_counts_by_org[count_result.organization_id] = count_result.user_count

    managers_by_org: dict[int, list[str]] = {}
    managers_stmt = (
        select(User.organization_id, User.name, User.phone, User.email)
        .where(
            User.organization_id.isnot(None),
            User.role.in_(tuple(SCHOOL_ADMIN_ROLES)),
            org_filter(scope, User.organization_id),
        )
        .order_by(User.organization_id, User.name)
    )
    managers_query = (await db.execute(managers_stmt)).all()

    for row in managers_query:
        org_id_key = cast(int, row.organization_id)
        display = row.name or row.phone or getattr(row, "email", None) or ""
        managers_by_org.setdefault(org_id_key, []).append(display)

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
                .where(panel_org_table_filter(scope))
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
            for org_key, org_stats in list(token_stats_by_org.items()):
                mindbot_totals = await aggregate_mindbot_token_totals(
                    db,
                    organization_id=int(org_key),
                )
                token_stats_by_org[org_key] = add_token_period(org_stats, mindbot_totals)
        except Exception as e:
            logger.debug("TokenUsage query failed: %s", e)

    for org in orgs:
        user_count = user_counts_by_org.get(org.id, 0)
        org_managers = managers_by_org.get(cast(int, org.id), [])
        manager_count = len(org_managers)
        org_token_stats = token_stats_by_org.get(org.id, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

        expires_at_val = cast(Optional[datetime], org.expires_at)
        created_at_val = cast(Optional[datetime], org.created_at)
        invite_raw = cast(Optional[str], org.invitation_code)
        invite_masked = mask_invitation_code(invite_raw)
        result.append(
            {
                "id": org.id,
                "code": org.code,
                "name": org.name,
                "display_name": getattr(org, "display_name", None),
                "invitation_code": "",
                "invitation_code_masked": invite_masked or "",
                "user_count": user_count,
                "manager_count": manager_count,
                "managers": org_managers,
                "expires_at": utc_to_beijing_iso(expires_at_val),
                "is_active": org.is_active if hasattr(org, "is_active") else True,
                "created_at": utc_to_beijing_iso(created_at_val),
                "token_stats": org_token_stats,
                **dify_list_fields(org),
                **mindmate_branding_list_fields(org),
                **org_privatization_list_field(org),
                **school_tier_list_fields(org, user_count),
            }
        )
    return result


@router.get("/admin/mindmate/dify-default")
async def get_mindmate_dify_default_admin(
    _request: Request,
    _scope: AdminScope = Depends(require_global_organizations_read),
):
    """Return masked global MindMate Dify credentials from .env."""
    return global_mindmate_dify_fields()


@router.post("/admin/mindmate-dify-health-draft")
async def post_mindmate_dify_health_draft_admin(
    request: Optional[dict] = Body(None),
    _scope: AdminScope = Depends(require_invite_org_create),
):
    """Probe Dify credentials for school create (draft body; no org id)."""
    body = request if isinstance(request, dict) else None
    return await probe_mindmate_dify_health_draft(body)


@router.post("/admin/organizations/{org_id}/mindmate-dify-health")
async def post_organization_mindmate_dify_health_admin(
    org_id: int,
    request: Optional[dict] = Body(None),
    _scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Probe effective MindMate Dify credentials (optional draft body; never exposes secrets)."""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    body = request if isinstance(request, dict) else None
    return await probe_mindmate_dify_health(org, body)


@router.get("/admin/organizations/{org_id}/invitation-code")
async def get_organization_invitation_code_admin(
    org_id: int,
    _request: Request,
    scope: AdminScope = Depends(get_admin_scope),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Return the invitation code for one organization."""
    scope.assert_any_capability(
        frozenset({CAP_TAB_ORGANIZATIONS_VIEW, CAP_TAB_INVITES_VIEW}),
        lang,
    )
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    assert_resource_org_in_scope(
        scope,
        org_id,
        lang,
        resource_invited_by_user_id=getattr(org, "invited_by_user_id", None),
    )
    logger.info(
        "[Auth] Admin user_id=%s read full invitation code for org_id=%s",
        scope.actor.id,
        org_id,
    )
    return {"invitation_code": cast(Optional[str], org.invitation_code) or ""}


@router.post("/admin/organizations")
async def create_organization_admin(
    request: dict,
    _http_request: Request,
    scope: AdminScope = Depends(require_invite_org_create),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Create new organization (superadmin, operations, or expert invite tab)."""
    current_user = scope.actor
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
        invited_by_user_id=int(current_user.id),
        created_at=datetime.now(UTC),
    )
    apply_dify_on_create(new_org, request, lang)
    apply_school_tier_on_create(
        new_org,
        request,
        allow_explicit_tier=is_superadmin(current_user),
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
            detail=Messages.error("failed_create_organization", lang),
        ) from e

    # Write to Redis cache SECOND (non-blocking)
    try:
        await org_cache.cache_org(new_org)
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


@router.put("/admin/organizations/{org_id}")
async def update_organization_admin(
    org_id: int,
    request: dict,
    _http_request: Request,
    scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Update organization (superadmin only)."""
    current_user = scope.actor
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

    if (
        "dify_api_base_url" in request
        or "dify_api_key" in request
        or "dify_timeout_seconds" in request
        or "show_chain_of_thought" in request
        or "show_chain_of_thought_oto" in request
        or "show_chain_of_thought_internal_group" in request
        or "show_chain_of_thought_cross_org_group" in request
        or "chain_of_thought_max_chars" in request
        or "dingtalk_ai_card_streaming_max_chars" in request
    ):
        apply_dify_on_update(org, request, lang)

    if "mindmate_agent_name" in request or "mindmate_agent_avatar_url" in request:
        apply_mindmate_branding_on_update(org, request, lang)

    quota_fields_changed = "school_tier" in request or "extra_member_seats" in request

    if "school_tier" in request:
        apply_school_tier_on_update(org, request, lang)

    if "extra_member_seats" in request:
        apply_extra_member_seats_on_update(org, request, lang)

    if quota_fields_changed:
        clear_extra_member_seats_if_trial(org)
        await assert_organization_tier_allows_current_managers(db, org, lang)
        await assert_organization_tier_allows_current_members(db, org, lang)

    await propagate_org_dify_settings_to_mindbot_configs(db, org)

    try:
        await db.commit()
        await db.refresh(org)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to update org ID %s in database: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_update_organization", lang),
        ) from e

    if not await org_cache.write_through(org, old_code, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org_id)
        await org_cache.recover_after_failed_write_through(org, old_code, old_invite)
    else:
        logger.info("[Auth] Updated and re-cached org ID %s", org_id)

    logger.info("Admin %s updated organization: %s", current_user.phone, org.code)
    updated_expires = cast(Optional[datetime], org.expires_at)
    updated_created = cast(Optional[datetime], org.created_at)
    member_count = await member_count_for_org(db, int(org.id))
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "display_name": getattr(org, "display_name", None),
        "invitation_code": org.invitation_code,
        "expires_at": updated_expires.isoformat() if updated_expires else None,
        "is_active": org.is_active if hasattr(org, "is_active") else True,
        "created_at": updated_created.isoformat() if updated_created else None,
        **dify_list_fields(org),
        **mindmate_branding_list_fields(org),
        **org_privatization_list_field(org),
        **school_tier_list_fields(org, member_count),
    }


@router.post("/admin/organizations/{org_id}/mindmate-avatar")
async def upload_organization_mindmate_avatar_admin(
    org_id: int,
    file: UploadFile = File(...),
    scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Upload MindMate agent avatar for one organization."""
    current_user = scope.actor
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    old_code = cast(Optional[str], org.code)
    old_invite = cast(Optional[str], org.invitation_code)
    old_avatar_url = cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None))
    avatar_url = await save_mindmate_agent_avatar(org, file)
    setattr(org, "mindmate_agent_avatar_url", avatar_url)

    try:
        await db.commit()
        await db.refresh(org)
    except Exception as exc:
        await db.rollback()
        revert_mindmate_avatar_upload(old_avatar_url, avatar_url)
        logger.error("[Auth] Failed to save MindMate avatar for org ID %s: %s", org_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_save_avatar", lang),
        ) from exc

    finalize_mindmate_avatar_upload(org_id, old_avatar_url, avatar_url)

    if not await org_cache.write_through(org, old_code, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org_id)
        await org_cache.recover_after_failed_write_through(org, old_code, old_invite)

    logger.info("Admin %s uploaded MindMate avatar for org_id=%s", current_user.phone, org_id)
    return {
        "mindmate_agent_avatar_url": avatar_url,
        **mindmate_branding_list_fields(org),
    }


@router.post("/admin/organizations/{org_id}/refresh-invitation-code")
async def refresh_organization_invitation_code(
    org_id: int,
    _request: Request,
    scope: AdminScope = Depends(require_invite_org_create),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Generate a new invitation code for the organization."""
    current_user = scope.actor
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        error_msg = Messages.error("organization_not_found", org_id, lang=lang)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

    assert_resource_org_in_scope(
        scope,
        org_id,
        lang,
        resource_invited_by_user_id=getattr(org, "invited_by_user_id", None),
    )

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
            detail=Messages.error("failed_refresh_invitation_code", lang),
        ) from e

    if not await org_cache.write_through(org, org_code_val, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org_id)
        await org_cache.recover_after_failed_write_through(org, org_code_val, old_invite)

    logger.info("Admin %s refreshed invitation code for org %s", current_user.phone, org.code)
    return {
        "id": org.id,
        "invitation_code": org.invitation_code,
    }


@router.delete("/admin/organizations/{org_id}")
async def delete_organization_admin(
    org_id: int,
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
    delete_users: bool = False,
):
    """Delete organization (superadmin only). Use delete_users=true to also remove all user accounts."""
    current_user = scope.actor
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
            await delete_user_fk_dependent_rows(db, uid)
            await user_cache.invalidate(uid, user.phone, getattr(user, "email", None))
            await db.delete(user)
        try:
            await db.flush()
        except Exception as e:
            await db.rollback()
            logger.error("[Auth] Failed to delete users for %s: %s", org_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=Messages.error("failed_delete_organization_users", lang),
            ) from e

    purge_org_mindmate_avatar_storage(org_id)

    await db.delete(org)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to delete org ID %s in database: %s", org_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_delete_organization", lang),
        ) from e

    try:
        await org_cache.invalidate(org_id, org_code, org_invite)
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


@router.get("/admin/managers")
async def list_all_managers(
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_read),
    db: AsyncSession = Depends(get_async_db),
    _lang: Language = Depends(get_language_dependency),
):
    """
    List all managers across all organizations (ADMIN ONLY).

    Returns managers with their organization info for the role control panel.
    """
    managers_stmt = (
        select(User)
        .where(
            User.organization_id.isnot(None),
            User.role.in_(tuple(SCHOOL_ADMIN_ROLES)),
            org_filter(scope, User.organization_id),
        )
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
        masked_phone = user.phone or ""
        if user.phone and len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]
        display_name = user.name or user.phone or getattr(user, "email", None) or ""
        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": display_name,
                "organization_id": user.organization_id,
                "organization_code": org.code if org else None,
                "organization_name": org.name if org else None,
                "created_at": utc_to_beijing_iso(user.created_at),
            }
        )

    return {"managers": result}


@router.get("/admin/organizations/{org_id}/users")
async def list_organization_users(
    org_id: int,
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_read),
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
    await assert_panel_org_readable(scope, org_id, db, lang)

    users_stmt = select(User).where(User.organization_id == org_id).order_by(User.name)
    users = (await db.execute(users_stmt)).scalars().all()

    result = []
    for user in users:
        # Get role (default to teacher if not set)
        role = getattr(user, "role", ROLE_TEACHER) or ROLE_TEACHER
        phone = user.phone or getattr(user, "email", None) or ""
        masked_phone = phone[:3] + "****" + phone[-4:] if user.phone and len(user.phone) == 11 else phone
        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": user.name or phone,
                "role": role,
                "is_manager": normalize_role(role) == "school_admin",
            }
        )

    return {
        "organization": {"id": org.id, "code": org.code, "name": org.name},
        "users": result,
    }


@router.get("/admin/organizations/{org_id}/managers")
async def list_organization_managers(
    org_id: int,
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_read),
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
    await assert_panel_org_readable(scope, org_id, db, lang)

    managers_stmt = (
        select(User).where(User.organization_id == org_id, User.role.in_(tuple(SCHOOL_ADMIN_ROLES))).order_by(User.name)
    )
    managers = (await db.execute(managers_stmt)).scalars().all()

    result = []
    for user in managers:
        phone = user.phone or getattr(user, "email", None) or ""
        masked_phone = phone[:3] + "****" + phone[-4:] if user.phone and len(user.phone) == 11 else phone
        result.append(
            {
                "id": user.id,
                "phone": masked_phone,
                "name": user.name or phone,
            }
        )

    return {
        "organization": {"id": org.id, "code": org.code, "name": org.name},
        "managers": result,
        "manager_count": len(result),
        "manager_limit": manager_limit_for_org(org),
    }


@router.put("/admin/organizations/{org_id}/managers/{user_id}")
async def set_organization_manager(
    org_id: int,
    user_id: int,
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Set a user as manager of their organization.

    The user must belong to the specified organization.
    """
    current_user = scope.actor
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

    if normalize_role(user.role) != "school_admin":
        await assert_organization_has_manager_capacity(db, org, lang)

    # Set role to manager
    user.role = "school_admin"

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to set manager role for user ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_set_manager_role", lang),
        ) from e

    # Invalidate user cache
    try:
        await user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
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


@router.delete("/admin/organizations/{org_id}/managers/{user_id}")
async def remove_organization_manager(
    org_id: int,
    user_id: int,
    _request: Request,
    scope: AdminScope = Depends(require_global_organizations_edit),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Remove manager role from a user.

    Resets the user's role back to teacher.
    """
    current_user = scope.actor
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

    # Reset role to teacher
    user.role = ROLE_TEACHER

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error("[Auth] Failed to remove manager role from user ID %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_remove_manager_role", lang),
        ) from e

    # Invalidate user cache
    try:
        await user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
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
