"""School subscription tier limits for B2B organizations."""

from __future__ import annotations

from typing import Any, Final

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User

from utils.auth.org_storage_estimate import org_diagram_storage_estimate
from models.domain.messages import Language, Messages

from services.redis.cache.redis_org_cache import org_cache
from utils.auth.role_constants import SCHOOL_ADMIN_ROLES
from utils.auth.roles import is_superadmin

SCHOOL_TIER_LITE: Final[str] = "lite"
SCHOOL_TIER_STANDARD: Final[str] = "standard"
SCHOOL_TIER_PROFESSIONAL: Final[str] = "professional"

SCHOOL_TIERS: Final[tuple[str, ...]] = (
    SCHOOL_TIER_LITE,
    SCHOOL_TIER_STANDARD,
    SCHOOL_TIER_PROFESSIONAL,
)

DEFAULT_SCHOOL_TIER: Final[str] = SCHOOL_TIER_STANDARD

_GIB = 1024**3

SCHOOL_TIER_LIMITS: Final[dict[str, dict[str, int]]] = {
    SCHOOL_TIER_LITE: {
        "member_limit": 50,
        "manager_limit": 1,
        "diagram_storage_bytes_per_member": 1 * _GIB,
    },
    SCHOOL_TIER_STANDARD: {
        "member_limit": 120,
        "manager_limit": 3,
        "diagram_storage_bytes_per_member": 2 * _GIB,
    },
    SCHOOL_TIER_PROFESSIONAL: {
        "member_limit": 200,
        "manager_limit": 5,
        "diagram_storage_bytes_per_member": 5 * _GIB,
    },
}


TIER_FEATURE_ONLINE_COLLAB: Final[str] = "online_collab"
TIER_FEATURE_CHROME_EXTENSION: Final[str] = "chrome_extension"
TIER_FEATURE_PRESENTATION_TOOLS: Final[str] = "presentation_tools"
TIER_FEATURE_API_TOKEN: Final[str] = "api_token"

_STANDARD_PLUS_FEATURES: Final[frozenset[str]] = frozenset(
    {
        TIER_FEATURE_ONLINE_COLLAB,
        TIER_FEATURE_CHROME_EXTENSION,
        TIER_FEATURE_PRESENTATION_TOOLS,
        TIER_FEATURE_API_TOKEN,
    }
)


def school_tier_allows_feature(tier: str, feature: str) -> bool:
    """Lite tier blocks collab, presentation tools, Chrome extension, and API tokens."""
    if feature not in _STANDARD_PLUS_FEATURES:
        return True
    return normalize_school_tier(tier) != SCHOOL_TIER_LITE


def school_tier_features_payload(tier: str) -> dict[str, bool]:
    """Feature flags derived from a school's tier slug."""
    allows_premium = normalize_school_tier(tier) != SCHOOL_TIER_LITE
    return {
        TIER_FEATURE_ONLINE_COLLAB: allows_premium,
        TIER_FEATURE_CHROME_EXTENSION: allows_premium,
        TIER_FEATURE_PRESENTATION_TOOLS: allows_premium,
        TIER_FEATURE_API_TOKEN: allows_premium,
    }


def school_tier_features_for_no_org() -> dict[str, bool]:
    """Personal / non-org accounts keep premium canvas features enabled."""
    return school_tier_features_payload(SCHOOL_TIER_PROFESSIONAL)


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
        return True
    tier = normalize_school_tier(getattr(org, "school_tier", None))
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


def normalize_school_tier(value: object | None) -> str:
    """Return a canonical tier slug; unknown values fall back to standard."""
    token = str(value or "").strip().lower()
    if token in SCHOOL_TIER_LIMITS:
        return token
    return DEFAULT_SCHOOL_TIER


def member_limit_for_org(org: Organization) -> int:
    """Member cap for the organization's current tier."""
    tier = normalize_school_tier(getattr(org, "school_tier", None))
    return int(SCHOOL_TIER_LIMITS[tier]["member_limit"])


def manager_limit_for_org(org: Organization) -> int:
    """School manager (school_admin) cap for the organization's current tier."""
    tier = normalize_school_tier(getattr(org, "school_tier", None))
    return int(SCHOOL_TIER_LIMITS[tier]["manager_limit"])


def diagram_storage_bytes_per_member_for_tier(tier: str) -> int:
    """Diagram storage allowance per member (bytes) for a tier slug."""
    normalized = normalize_school_tier(tier)
    return int(SCHOOL_TIER_LIMITS[normalized]["diagram_storage_bytes_per_member"])


def diagram_storage_limit_bytes_for_org(org: Organization, member_count: int) -> int:
    """Diagram storage cap (bytes) = tier GB per member × current member count."""
    per_member = diagram_storage_bytes_per_member_for_tier(normalize_school_tier(getattr(org, "school_tier", None)))
    return per_member * max(int(member_count), 0)


def school_tier_list_fields(org: Organization, member_count: int) -> dict[str, Any]:
    """API fields derived from the organization's school tier."""
    tier = normalize_school_tier(getattr(org, "school_tier", None))
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


def apply_school_tier_on_create(org: Organization, request: dict) -> None:
    """Apply optional school_tier when creating an organization."""
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
    tier = normalize_school_tier(getattr(org, "school_tier", None))
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
    current_count = await member_count_for_org(db, int(org.id))
    if current_count > limit:
        error_msg = Messages.error(
            "organization_member_limit_exceeded_for_tier",
            lang,
            current_count,
            limit,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
