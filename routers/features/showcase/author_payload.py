"""Showcase author display payloads (RLS-safe across orgs)."""

from __future__ import annotations

from sqlalchemy import select

from models.domain.auth import Organization, User
from models.domain.showcase import ShowcasePost
from utils.db.rls_context import RlsContext, rls_async_session


async def load_public_author_profiles(author_ids: set[int]) -> dict[int, dict]:
    """
    Load public author display fields when ``users`` RLS hides cross-org rows.

    Showcase posts are community-readable across orgs, but ``joinedload(author)``
    only returns same-org users under authenticated RLS. Resolve missing authors
    under system bootstrap and return only name/avatar/organization.
    """
    if not author_ids:
        return {}
    async with rls_async_session(RlsContext.system_bootstrap()) as sys_db:
        rows = (
            await sys_db.execute(
                select(
                    User.id,
                    User.name,
                    User.avatar,
                    Organization.name.label("organization_name"),
                )
                .outerjoin(Organization, User.organization_id == Organization.id)
                .where(User.id.in_(author_ids))
            )
        ).all()
    profiles: dict[int, dict] = {}
    for row in rows:
        org_name = row.organization_name
        profiles[int(row.id)] = {
            "name": row.name,
            "avatar": row.avatar,
            "organization": org_name if isinstance(org_name, str) and org_name.strip() else None,
        }
    return profiles


def _author_display_name(author: User | None, profile: dict | None) -> str:
    if author is not None and author.name:
        return author.name
    if profile:
        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "Anonymous"


def _author_display_avatar(author: User | None, profile: dict | None) -> str:
    if author is not None and author.avatar:
        return author.avatar
    if profile:
        avatar = profile.get("avatar")
        if isinstance(avatar, str) and avatar.strip():
            return avatar.strip()
    return "👤"


def _author_display_organization(author: User | None, profile: dict | None) -> str | None:
    if author is not None and author.organization:
        return author.organization.name
    if profile:
        org = profile.get("organization")
        if isinstance(org, str) and org.strip():
            return org.strip()
    return None


def author_payload(post: ShowcasePost, author_profile: dict | None = None) -> dict:
    """Build author JSON; tolerate missing ``post.author`` (RLS or deleted user)."""
    attr = post.attribution if isinstance(post.attribution, dict) else {}
    author = post.author
    if post.publish_source == "proxy" and isinstance(attr.get("display_name"), str) and attr["display_name"].strip():
        org = attr.get("organization")
        org_str = org.strip() if isinstance(org, str) and org.strip() else None
        if org_str is None:
            org_str = _author_display_organization(author, author_profile)
        return {
            "id": post.author_id,
            "name": attr["display_name"].strip(),
            "avatar": _author_display_avatar(author, author_profile),
            "organization": org_str,
            "is_proxy": True,
        }
    return {
        "id": post.author_id,
        "name": _author_display_name(author, author_profile),
        "avatar": _author_display_avatar(author, author_profile),
        "organization": _author_display_organization(author, author_profile),
        "is_proxy": False,
    }
