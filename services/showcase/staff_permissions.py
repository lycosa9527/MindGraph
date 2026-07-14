"""
Showcase staff permission resolution (grants + platform roles).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.showcase import ShowcasePost
from models.domain.showcase_admin import ShowcaseStaffGrant
from utils.auth.roles import is_expert, is_platform_bd, is_superadmin

PERM_DASHBOARD = "showcase.dashboard.view"
PERM_REVIEW = "showcase.review"
PERM_DELETE = "showcase.delete"
PERM_RECOMMEND = "showcase.recommend"
PERM_PUBLISH_PROXY = "showcase.publish_proxy"
PERM_FIELDS = "showcase.fields.manage"
PERM_PERMISSIONS = "showcase.permissions.manage"

ALL_SHOWCASE_PERMS: frozenset[str] = frozenset(
    {
        PERM_DASHBOARD,
        PERM_REVIEW,
        PERM_DELETE,
        PERM_RECOMMEND,
        PERM_PUBLISH_PROXY,
        PERM_FIELDS,
        PERM_PERMISSIONS,
    }
)

PLATFORM_BD_DEFAULT: frozenset[str] = ALL_SHOWCASE_PERMS - frozenset({PERM_PERMISSIONS})

VALID_GRANT_PERMISSIONS: frozenset[str] = ALL_SHOWCASE_PERMS


def showcase_panel_capabilities(perms: frozenset[str]) -> frozenset[str]:
    """Map business permissions to admin panel capability keys for the UI."""
    caps: set[str] = set()
    if not perms:
        return frozenset()
    caps.add("tab.showcase.view")
    if PERM_REVIEW in perms or PERM_DELETE in perms or PERM_PUBLISH_PROXY in perms:
        caps.add("tab.showcase.edit")
    if PERM_RECOMMEND in perms:
        caps.add("tab.showcase.recommend")
    if PERM_FIELDS in perms:
        caps.add("tab.showcase.fields")
    if PERM_PERMISSIONS in perms:
        caps.add("tab.showcase.permissions")
    if PERM_DASHBOARD in perms or PERM_REVIEW in perms:
        caps.add("tab.showcase.dashboard")
    return frozenset(caps)


async def load_user_showcase_permissions(db: AsyncSession, user: User) -> frozenset[str]:
    if is_superadmin(user):
        return ALL_SHOWCASE_PERMS
    perms: set[str] = set()
    if is_platform_bd(user):
        perms |= PLATFORM_BD_DEFAULT
    if is_expert(user):
        perms.add(PERM_RECOMMEND)

    now = datetime.now(UTC)
    row = (
        await db.execute(select(ShowcaseStaffGrant).where(ShowcaseStaffGrant.user_id == user.id))
    ).scalar_one_or_none()
    if row and row.permissions:
        if row.expires_at is None or row.expires_at.replace(tzinfo=UTC) >= now:
            for item in row.permissions:
                if isinstance(item, str) and item in VALID_GRANT_PERMISSIONS:
                    perms.add(item)
    return frozenset(perms)


def user_has_showcase_permission(perms: frozenset[str], perm: str) -> bool:
    return perm in perms


async def can_publish_case(_user: User) -> bool:
    return True


async def can_publish_proxy(db: AsyncSession, user: User) -> bool:
    perms = await load_user_showcase_permissions(db, user)
    return PERM_PUBLISH_PROXY in perms


async def can_review_case(db: AsyncSession, user: User) -> bool:
    perms = await load_user_showcase_permissions(db, user)
    return PERM_REVIEW in perms


async def can_delete_case(_post: ShowcasePost, user: User, db: AsyncSession) -> bool:
    """Hard delete — staff with delete permission only (admin published management)."""
    perms = await load_user_showcase_permissions(db, user)
    return PERM_DELETE in perms


def can_withdraw_case(post: ShowcasePost, user: User) -> bool:
    """Author may withdraw a case still under review."""
    return post.author_id == user.id and post.status == "pending"


def can_delist_case(post: ShowcasePost, user: User) -> bool:
    """Author may delist an approved case from the public gallery."""
    return post.author_id == user.id and post.status == "approved"


async def can_edit_case(post: ShowcasePost, user: User, db: AsyncSession) -> bool:
    """Staff/authors may edit pending or rejected cases; approved posts are immutable here."""
    if post.status not in ("pending", "rejected"):
        return False
    perms = await load_user_showcase_permissions(db, user)
    if PERM_DELETE in perms or PERM_REVIEW in perms:
        return True
    if post.author_id == user.id:
        return True
    return False


def can_resubmit_case(post: ShowcasePost, user: User) -> bool:
    """Author may edit and resubmit a rejected case."""
    return post.author_id == user.id and post.status == "rejected"


async def can_expert_recommend(db: AsyncSession, user: User) -> bool:
    perms = await load_user_showcase_permissions(db, user)
    return PERM_RECOMMEND in perms


async def can_view_case_staff_meta(db: AsyncSession, user: User) -> bool:
    """Staff-only fields on posts (reviewer, expert recommender, etc.)."""
    perms = await load_user_showcase_permissions(db, user)
    return bool(perms)


async def can_manage_fields(db: AsyncSession, user: User) -> bool:
    perms = await load_user_showcase_permissions(db, user)
    return PERM_FIELDS in perms


async def can_manage_permissions(db: AsyncSession, user: User) -> bool:
    perms = await load_user_showcase_permissions(db, user)
    return PERM_PERMISSIONS in perms


async def can_view_dashboard(db: AsyncSession, user: User) -> bool:
    perms = await load_user_showcase_permissions(db, user)
    return PERM_DASHBOARD in perms or PERM_REVIEW in perms or PERM_DELETE in perms


async def can_user_review_post(post: ShowcasePost, user: User, db: AsyncSession) -> bool:
    if not await can_review_case(db, user):
        return False
    submitter_id = post.submitted_by_id if post.submitted_by_id is not None else post.author_id
    if submitter_id == user.id:
        return False
    if post.publish_source == "self" and post.author_id == user.id:
        return False
    return True


async def can_view_non_approved_post(post: ShowcasePost, user: User, db: AsyncSession) -> bool:
    if user.id in (post.author_id, post.submitted_by_id):
        return True
    return await can_review_case(db, user)
