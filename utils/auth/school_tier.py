"""School subscription tier limits and quota enforcement for B2B organizations."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages

from services.redis.cache.redis_org_cache import org_cache
from utils.auth.org_storage_estimate import org_diagram_storage_estimate
from utils.auth.role_constants import SCHOOL_ADMIN_ROLES
from utils.auth.roles import is_superadmin
from utils.auth import school_tier_defs
from utils.auth.school_tier_defs import (
    DEFAULT_SCHOOL_TIER,
    SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED,
    SCHOOL_TIER_LIMITS,
    diagram_storage_bytes_per_member_for_tier,
    is_unlimited_member_limit,
    max_diagrams_for_tier,
    normalize_school_tier,
    school_tier_allows_feature,
    school_tier_features_payload,
)
from utils.auth.school_tier_effective import effective_school_tier_for_org

DIAGRAM_SAVE_LIMIT_ERROR_PREFIX = school_tier_defs.DIAGRAM_SAVE_LIMIT_ERROR_PREFIX
SCHOOL_TIER_LITE = school_tier_defs.SCHOOL_TIER_LITE
SCHOOL_TIER_MEMBER_LIMIT_UNLIMITED = school_tier_defs.SCHOOL_TIER_MEMBER_LIMIT_UNLIMITED
SCHOOL_TIER_PROFESSIONAL = school_tier_defs.SCHOOL_TIER_PROFESSIONAL
SCHOOL_TIER_STANDARD = school_tier_defs.SCHOOL_TIER_STANDARD
SCHOOL_TIER_TRIAL = school_tier_defs.SCHOOL_TIER_TRIAL
SCHOOL_TIERS = school_tier_defs.SCHOOL_TIERS
TIER_FEATURE_API_TOKEN = school_tier_defs.TIER_FEATURE_API_TOKEN
TIER_FEATURE_CHROME_EXTENSION = school_tier_defs.TIER_FEATURE_CHROME_EXTENSION
TIER_FEATURE_ONLINE_COLLAB = school_tier_defs.TIER_FEATURE_ONLINE_COLLAB
TIER_FEATURE_PRESENTATION_TOOLS = school_tier_defs.TIER_FEATURE_PRESENTATION_TOOLS
diagram_limit_reached_message = school_tier_defs.diagram_limit_reached_message
format_diagram_save_limit_error = school_tier_defs.format_diagram_save_limit_error
is_manager_assignment_unavailable = school_tier_defs.is_manager_assignment_unavailable
is_unlimited_diagram_limit = school_tier_defs.is_unlimited_diagram_limit
parse_diagram_save_limit_error = school_tier_defs.parse_diagram_save_limit_error
school_tier_features_for_no_org = school_tier_defs.school_tier_features_for_no_org


async def _organization_for_user(db: AsyncSession, user: User) -> Organization | None:
    org_id = getattr(user, "organization_id", None)
    if org_id is None:
        return None
    org = await org_cache.get_by_id(org_id)
    if org is not None:
        return org
    return (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()


async def user_has_school_tier_feature(
    db: AsyncSession,
    user: User,
    feature: str,
) -> bool:
    """Whether the user's school tier allows a premium feature."""
    if is_superadmin(user):
        return True
    org_id = getattr(user, "organization_id", None)
    if org_id is None:
        return True
    org = await _organization_for_user(db, user)
    if org is None:
        return False
    tier = effective_school_tier_for_org(org)
    return school_tier_allows_feature(tier, feature)


async def assert_user_has_school_tier_feature(
    db: AsyncSession,
    user: User,
    feature: str,
    lang: Language,
) -> None:
    """Raise HTTP 403 when the user's school tier blocks the feature."""
    if await user_has_school_tier_feature(db, user, feature):
        return
    error_msg = Messages.error("school_tier_feature_unavailable", lang)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


def member_limit_for_org(org: Organization) -> int:
    """Member cap for the organization's current tier (0 = unlimited)."""
    tier = effective_school_tier_for_org(org)
    return int(SCHOOL_TIER_LIMITS[tier]["member_limit"])


def manager_limit_for_org(org: Organization) -> int:
    """School manager (school_admin) cap for the organization's current tier."""
    tier = effective_school_tier_for_org(org)
    return int(SCHOOL_TIER_LIMITS[tier]["manager_limit"])


def diagram_storage_limit_bytes_for_org(org: Organization, member_count: int) -> int:
    """Diagram storage cap (bytes) = tier GB per member × current member count."""
    per_member = diagram_storage_bytes_per_member_for_tier(effective_school_tier_for_org(org))
    return per_member * max(int(member_count), 0)


async def max_diagrams_for_user(db: AsyncSession, user: User) -> int:
    """Saved-diagram cap for a user based on org tier (non-org users: unlimited)."""
    org_id = getattr(user, "organization_id", None)
    if org_id is None:
        return SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED
    org = await _organization_for_user(db, user)
    if org is None:
        return max_diagrams_for_tier(DEFAULT_SCHOOL_TIER)
    return max_diagrams_for_tier(effective_school_tier_for_org(org))


async def max_diagrams_for_user_id(db: AsyncSession, user_id: int) -> int:
    """Saved-diagram cap resolved from a user id (unlimited when user/org missing)."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return SCHOOL_TIER_DIAGRAM_LIMIT_UNLIMITED
    return await max_diagrams_for_user(db, user)


def school_tier_list_fields(org: Organization, member_count: int) -> dict[str, Any]:
    """API fields derived from the organization's school tier."""
    tier = effective_school_tier_for_org(org)
    limits = SCHOOL_TIER_LIMITS[tier]
    per_member_bytes = int(limits["diagram_storage_bytes_per_member"])
    return {
        "school_tier": tier,
        "school_tier_member_limit": int(limits["member_limit"]),
        "school_tier_manager_limit": int(limits["manager_limit"]),
        "school_tier_diagram_storage_bytes_per_member": per_member_bytes,
        "school_tier_diagram_storage_bytes": diagram_storage_limit_bytes_for_org(
            org,
            member_count,
        ),
        "school_tier_features": school_tier_features_payload(tier),
    }


def apply_school_tier_on_create(
    org: Organization,
    request: dict,
    *,
    allow_explicit_tier: bool = False,
) -> None:
    """Apply school_tier when creating an organization (defaults to trial).

    Non-superadmin invite flows must not set paid tiers; only ``allow_explicit_tier``
    (superadmin) may honor ``school_tier`` in the request body.
    """
    if not allow_explicit_tier:
        setattr(org, "school_tier", DEFAULT_SCHOOL_TIER)
        return
    if "school_tier" not in request:
        setattr(org, "school_tier", DEFAULT_SCHOOL_TIER)
        return
    setattr(org, "school_tier", normalize_school_tier(request.get("school_tier")))


def apply_school_tier_on_update(org: Organization, request: dict, lang: Language) -> None:
    """Validate and apply school_tier on organization update."""
    if "school_tier" not in request:
        return
    raw = request.get("school_tier")
    if raw is None:
        setattr(org, "school_tier", DEFAULT_SCHOOL_TIER)
        return
    token = str(raw).strip().lower()
    if token not in SCHOOL_TIER_LIMITS:
        error_msg = Messages.error("invalid_school_tier", lang, token)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    setattr(org, "school_tier", token)


async def manager_count_for_org(db: AsyncSession, org_id: int) -> int:
    """Count school_admin managers for an organization."""
    stmt = select(func.count(User.id)).where(
        User.organization_id == org_id,
        User.role.in_(tuple(SCHOOL_ADMIN_ROLES)),
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def member_count_for_org(db: AsyncSession, org_id: int) -> int:
    """Count members (users) for an organization."""
    stmt = select(func.count(User.id)).where(User.organization_id == org_id)
    return int((await db.execute(stmt)).scalar_one() or 0)


async def school_dashboard_quotas_payload(
    db: AsyncSession,
    org: Organization,
) -> dict[str, Any]:
    """Quota usage and tier limits for the school dashboard."""
    org_id = int(org.id)
    tier = effective_school_tier_for_org(org)
    member_count = await member_count_for_org(db, org_id)
    manager_count = await manager_count_for_org(db, org_id)
    storage_estimate = await org_diagram_storage_estimate(db, org_id)
    storage_limit_bytes = diagram_storage_limit_bytes_for_org(org, member_count)
    return {
        "school_tier": tier,
        "member_count": member_count,
        "member_limit": member_limit_for_org(org),
        "manager_count": manager_count,
        "manager_limit": manager_limit_for_org(org),
        "storage_used_bytes": storage_estimate["total_bytes"],
        "storage_limit_bytes": storage_limit_bytes,
        "storage_breakdown": {
            "diagrams_bytes": storage_estimate["diagrams_bytes"],
            "snapshots_bytes": storage_estimate["snapshots_bytes"],
            "shared_diagrams_bytes": storage_estimate["shared_diagrams_bytes"],
        },
        "storage_is_estimate": True,
    }


async def assert_organization_has_member_capacity(
    db: AsyncSession,
    org: Organization,
    lang: Language,
    *,
    exclude_user_id: int | None = None,
) -> None:
    """Reject when the organization has reached its tier member limit."""
    limit = member_limit_for_org(org)
    if is_unlimited_member_limit(limit):
        return
    stmt = select(func.count(User.id)).where(User.organization_id == org.id)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    current_count = int((await db.execute(stmt)).scalar_one() or 0)
    if current_count >= limit:
        error_msg = Messages.error("organization_member_limit_reached", lang, limit)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


async def assert_organization_has_manager_capacity(
    db: AsyncSession,
    org: Organization,
    lang: Language,
) -> None:
    """Reject when the organization has reached its tier school-manager limit."""
    limit = manager_limit_for_org(org)
    current_count = await manager_count_for_org(db, int(org.id))
    if current_count >= limit:
        error_msg = Messages.error("organization_manager_limit_reached", lang, limit)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


async def assert_organization_tier_allows_current_managers(
    db: AsyncSession,
    org: Organization,
    lang: Language,
) -> None:
    """Reject tier changes that would leave more managers than the new tier allows."""
    limit = manager_limit_for_org(org)
    current_count = await manager_count_for_org(db, int(org.id))
    if current_count > limit:
        error_msg = Messages.error(
            "organization_manager_limit_exceeded_for_tier",
            lang,
            current_count,
            limit,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)


async def assert_organization_tier_allows_current_members(
    db: AsyncSession,
    org: Organization,
    lang: Language,
) -> None:
    """Reject tier changes that would leave more members than the new tier allows."""
    limit = member_limit_for_org(org)
    if is_unlimited_member_limit(limit):
        return
    current_count = await member_count_for_org(db, int(org.id))
    if current_count > limit:
        error_msg = Messages.error(
            "organization_member_limit_exceeded_for_tier",
            lang,
            current_count,
            limit,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
