"""
Mobile organization branding edits.

Phone admins who can create a school may update only the public MindMate
identity of a school they can already see on the mobile list: agent name,
alias, display name, and avatar. Dify credentials, tiers, codes, and the
internal organization name stay on the desktop superadmin update.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional, cast

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import MINDMATE_AGENT_NAME_MAX_LENGTH, Organization
from models.domain.messages import Language, Messages
from routers.auth.dependencies import get_async_db_with_request_rls, get_language_dependency, require_invite_org_create
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_scope import AdminScope
from utils.auth.roles import is_superadmin

from .organization_mindmate_branding import (
    apply_mindmate_branding_on_update,
    delete_local_mindmate_avatar,
    finalize_mindmate_avatar_upload,
    mindmate_branding_list_fields,
    purge_org_mindmate_avatar_storage,
    revert_mindmate_avatar_upload,
    save_mindmate_agent_avatar,
)

logger = logging.getLogger(__name__)

router = APIRouter()

SCHOOL_DISPLAY_NAME_MAX_LENGTH = 200
_TEXT_FIELDS = frozenset({"mindmate_agent_name", "mindmate_agent_alias", "display_name"})
_ALLOWED_FIELDS = _TEXT_FIELDS | frozenset({"mindmate_agent_avatar_url"})
_AGENT_LIMITS = {
    "mindmate_agent_name": ("mindmate_agent_name_too_long", MINDMATE_AGENT_NAME_MAX_LENGTH),
    "mindmate_agent_alias": ("mindmate_agent_alias_too_long", MINDMATE_AGENT_NAME_MAX_LENGTH),
}


def _invalid(lang: Language) -> HTTPException:
    """Reject a branding payload that is not the phone editor's whitelist."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=Messages.error("invalid_request", lang=lang),
    )


def _optional_text(value: object, lang: Language) -> Optional[str]:
    """Strip a branding string. Non-strings are rejected."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid(lang)
    stripped = value.strip()
    return stripped or None


def parse_mobile_branding_body(request: object, lang: Language) -> dict[str, Optional[str]]:
    """Keep only agent name, alias, display name, and an avatar clear."""
    if not isinstance(request, dict) or not request:
        raise _invalid(lang)
    unknown = set(request) - _ALLOWED_FIELDS
    if unknown:
        raise _invalid(lang)

    parsed: dict[str, Optional[str]] = {}
    for field in _TEXT_FIELDS:
        if field not in request:
            continue
        parsed[field] = _optional_text(request.get(field), lang)

    if "mindmate_agent_avatar_url" in request:
        if request.get("mindmate_agent_avatar_url") is not None:
            raise _invalid(lang)
        parsed["mindmate_agent_avatar_url"] = None

    for field, (error_key, limit) in _AGENT_LIMITS.items():
        value = parsed.get(field)
        if value and len(value) > limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error(error_key, lang=lang),
            )

    display_name = parsed.get("display_name")
    if display_name and len(display_name) > SCHOOL_DISPLAY_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error(
                "organization_display_name_too_long",
                SCHOOL_DISPLAY_NAME_MAX_LENGTH,
                lang=lang,
            ),
        )
    return parsed


def assert_mobile_created_org(scope: AdminScope, org: object, lang: Language) -> None:
    """Superadmin may edit any school. Everyone else may edit only schools they created."""
    if is_superadmin(scope.actor):
        return
    actor_id = getattr(scope.actor, "id", None)
    invited_by = getattr(org, "invited_by_user_id", None)
    org_id = cast(int, getattr(org, "id", 0))
    if actor_id is None or invited_by is None or int(invited_by) != int(actor_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", org_id, lang=lang),
        )


def _branding_response(org: Organization) -> dict:
    """Public branding fields the phone form reloads."""
    display_raw = getattr(org, "display_name", None)
    display_name = str(display_raw).strip() if display_raw else ""
    return {
        "id": org.id,
        "name": org.name,
        "display_name": display_name or None,
        **mindmate_branding_list_fields(org),
    }


async def _load_org(db: AsyncSession, org_id: int, lang: Language) -> Organization:
    """Load one organization or 404."""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", org_id, lang=lang),
        )
    return org


async def _commit_org_write(
    db: AsyncSession,
    org: Organization,
    old_code: Optional[str],
    old_invite: Optional[str],
    lang: Language,
) -> None:
    """Commit the organization row and refresh the org cache."""
    try:
        await db.commit()
        await db.refresh(org)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Auth] Failed to update mobile branding for org ID %s: %s", org.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_update_organization", lang=lang),
        ) from exc

    if not await org_cache.write_through(org, old_code, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org.id)
        await org_cache.recover_after_failed_write_through(org, old_code, old_invite)


def _apply_branding(org: Organization, parsed: dict[str, Optional[str]], lang: Language) -> None:
    """Write the whitelisted branding fields onto the organization.

    Avatar files stay on disk until the row commit succeeds. Clearing the URL
    here only updates the column; the caller deletes the file afterward.
    """
    text_keys = ("mindmate_agent_name", "mindmate_agent_alias")
    text_update = {key: parsed[key] for key in text_keys if key in parsed}
    if text_update:
        apply_mindmate_branding_on_update(org, text_update, lang)
    if "display_name" in parsed:
        setattr(org, "display_name", parsed["display_name"])
    if "mindmate_agent_avatar_url" in parsed:
        setattr(org, "mindmate_agent_avatar_url", None)


def _delete_cleared_avatar(org_id: int, old_avatar_url: Optional[str]) -> None:
    """Remove avatar files after the cleared URL has been committed."""
    delete_local_mindmate_avatar(old_avatar_url)
    purge_org_mindmate_avatar_storage(org_id)


@router.patch("/admin/mobile/organizations/{org_id}/branding")
async def update_mobile_organization_branding(
    org_id: int,
    request: dict,
    scope: AdminScope = Depends(require_invite_org_create),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    lang: Language = Depends(get_language_dependency),
):
    """Update MindMate name, alias, display name, or clear the avatar."""
    parsed = parse_mobile_branding_body(request, lang)
    org = await _load_org(db, org_id, lang)
    assert_mobile_created_org(scope, org, lang)

    old_code = cast(Optional[str], org.code)
    old_invite = cast(Optional[str], org.invitation_code)
    clearing_avatar = "mindmate_agent_avatar_url" in parsed
    old_avatar_url = cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None)) if clearing_avatar else None
    _apply_branding(org, parsed, lang)
    await _commit_org_write(db, org, old_code, old_invite, lang)
    if clearing_avatar:
        _delete_cleared_avatar(org_id, old_avatar_url)
    logger.info(
        "Admin %s updated mobile branding for org_id=%s",
        getattr(scope.actor, "phone", None),
        org_id,
    )
    return _branding_response(org)


@router.post("/admin/mobile/organizations/{org_id}/mindmate-avatar")
async def upload_mobile_organization_mindmate_avatar(
    org_id: int,
    file: UploadFile = File(...),
    scope: AdminScope = Depends(require_invite_org_create),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    lang: Language = Depends(get_language_dependency),
):
    """Upload the MindMate avatar for a school the phone admin can manage."""
    org = await _load_org(db, org_id, lang)
    assert_mobile_created_org(scope, org, lang)

    old_code = cast(Optional[str], org.code)
    old_invite = cast(Optional[str], org.invitation_code)
    old_avatar_url = cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None))
    avatar_url = await save_mindmate_agent_avatar(org, file)
    setattr(org, "mindmate_agent_avatar_url", avatar_url)

    try:
        await db.commit()
        await db.refresh(org)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        revert_mindmate_avatar_upload(old_avatar_url, avatar_url)
        logger.error("[Auth] Failed to save mobile MindMate avatar for org ID %s: %s", org_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_save_avatar", lang=lang),
        ) from exc

    finalize_mindmate_avatar_upload(org_id, old_avatar_url, avatar_url)
    if not await org_cache.write_through(org, old_code, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org_id)
        await org_cache.recover_after_failed_write_through(org, old_code, old_invite)

    logger.info(
        "Admin %s uploaded mobile MindMate avatar for org_id=%s",
        getattr(scope.actor, "phone", None),
        org_id,
    )
    return _branding_response(org)
