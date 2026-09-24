"""
Who may see a diagram in their library, and who may write it.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.diagram_folders import DiagramFolder
from models.domain.diagram_shares import DiagramShare
from models.domain.diagrams import Diagram
from services.diagram_shares.lease import drop_user_lease, lease_head
from services.utils.error_types import DATABASE_ERRORS
from services.utils.typing_helpers import result_rowcount
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)


@dataclass
class LibraryAccess:
    """Owner, recipient, or no library access."""

    role: str
    owner_user_id: Optional[int]


def items_missing_share_role(items: list[dict[str, Any]]) -> bool:
    """True when a cached library list predates share metadata."""
    return any(not isinstance(item, dict) or "share_role" not in item for item in items)


def share_membership_delta(current: set[int], desired: set[int]) -> tuple[set[int], set[int]]:
    """User ids to add and user ids to remove when the share dialog is saved."""
    return desired - current, current - desired


async def library_access(user_id: int, diagram_id: str) -> LibraryAccess:
    """Resolve owner vs recipient. Missing diagrams are role ``none``."""
    async with user_rls_session(user_id) as db:
        try:
            result = await db.execute(
                select(Diagram.user_id).where(Diagram.id == diagram_id, Diagram.is_deleted.is_(False))
            )
            owner_id = result.scalar_one_or_none()
            if owner_id is None:
                return LibraryAccess(role="none", owner_user_id=None)
            if int(owner_id) == user_id:
                return LibraryAccess(role="owner", owner_user_id=int(owner_id))
            grant = await db.execute(
                select(DiagramShare.id).where(
                    DiagramShare.diagram_id == diagram_id,
                    DiagramShare.grantee_user_id == user_id,
                )
            )
            if grant.scalar_one_or_none() is None:
                return LibraryAccess(role="none", owner_user_id=None)
            return LibraryAccess(role="recipient", owner_user_id=int(owner_id))
        except DATABASE_ERRORS as exc:
            logger.warning("[DiagramShare] access lookup failed diagram=%s: %s", diagram_id, exc)
            return LibraryAccess(role="none", owner_user_id=None)


async def diagram_has_grants(user_id: int, diagram_id: str) -> bool:
    """True when the owner has sent this diagram to at least one person."""
    async with user_rls_session(user_id) as db:
        try:
            result = await db.execute(select(DiagramShare.id).where(DiagramShare.diagram_id == diagram_id).limit(1))
            return result.scalar_one_or_none() is not None
        except DATABASE_ERRORS as exc:
            logger.warning("[DiagramShare] grant check failed diagram=%s: %s", diagram_id, exc)
            return False


async def spec_write_owner_id(
    user_id: int,
    diagram_id: str,
    tab_id: Optional[str] = None,
) -> tuple[Optional[int], str]:
    """
    Return ``(owner_user_id, "")`` when this user may write title/spec.

    Error codes are ``missing`` and ``viewer``. A tab id is checked when the
    canvas sends one, so a later tab of the editor cannot overwrite the spec.
    """
    access = await library_access(user_id, diagram_id)
    if access.role == "none" or access.owner_user_id is None:
        return None, "missing"
    head = await lease_head(diagram_id)
    if head is None:
        if access.role == "owner":
            return access.owner_user_id, ""
        return None, "viewer"
    if head.user_id != user_id:
        return None, "viewer"
    if tab_id and tab_id != head.tab_id:
        return None, "viewer"
    return access.owner_user_id, ""


async def grantee_user_ids(owner_user_id: int, diagram_id: str) -> list[int]:
    """Recipient user ids for list-cache invalidation."""
    async with user_rls_session(owner_user_id) as db:
        try:
            result = await db.execute(select(DiagramShare.grantee_user_id).where(DiagramShare.diagram_id == diagram_id))
            return [int(row[0]) for row in result.all()]
        except DATABASE_ERRORS as exc:
            logger.warning("[DiagramShare] grantee list failed diagram=%s: %s", diagram_id, exc)
            return []


async def annotate_library_shares(
    db: AsyncSession,
    user_id: int,
    items: list[dict[str, Any]],
    source_channel: Optional[str] = None,
) -> None:
    """Mark owned rows and append diagrams shared to this user."""
    for item in items:
        item["share_role"] = "owner"
        item["shared"] = False
    owned_ids = [str(item.get("id") or "") for item in items if item.get("id")]
    try:
        if owned_ids:
            granted = await db.execute(
                select(DiagramShare.diagram_id).where(DiagramShare.diagram_id.in_(owned_ids)).distinct()
            )
            granted_ids = {str(row[0]) for row in granted.all()}
            for item in items:
                if str(item.get("id") or "") in granted_ids:
                    item["shared"] = True
        received = await db.execute(
            select(Diagram, DiagramShare)
            .join(DiagramShare, DiagramShare.diagram_id == Diagram.id)
            .where(
                DiagramShare.grantee_user_id == user_id,
                Diagram.is_deleted.is_(False),
            )
        )
        for diagram, share in received.all():
            channel = getattr(diagram, "source_channel", None)
            if source_channel and channel != source_channel:
                continue
            updated_at = getattr(diagram, "updated_at", None)
            expires_at = getattr(diagram, "workshop_expires_at", None)
            items.append(
                {
                    "id": getattr(diagram, "id", ""),
                    "title": getattr(diagram, "title", ""),
                    "diagram_type": getattr(diagram, "diagram_type", ""),
                    "thumbnail": getattr(diagram, "thumbnail", None),
                    "updated_at": updated_at.isoformat() if updated_at is not None else None,
                    "is_pinned": bool(share.is_pinned),
                    "folder_id": share.folder_id,
                    "source_channel": channel,
                    "workshop_code": getattr(diagram, "workshop_code", None) or None,
                    "workshop_expires_at": expires_at.isoformat() if expires_at is not None else None,
                    "share_role": "recipient",
                    "shared": True,
                }
            )
    except DATABASE_ERRORS as exc:
        logger.warning("[DiagramShare] library annotate failed user=%s: %s", user_id, exc)


async def replace_share_set(
    owner: User,
    diagram_id: str,
    user_ids: list[int],
) -> tuple[bool, str, set[int]]:
    """Replace the recipient set. Returns ``(ok, error_code, affected_user_ids)``."""
    org_id = getattr(owner, "organization_id", None)
    if org_id is None:
        return False, "no_org", set()
    desired = {int(user_id) for user_id in user_ids if int(user_id) != int(owner.id)}
    async with user_rls_session(int(owner.id), org_id) as db:
        try:
            owned = await db.execute(
                select(Diagram.id).where(
                    Diagram.id == diagram_id,
                    Diagram.user_id == owner.id,
                    Diagram.is_deleted.is_(False),
                )
            )
            if owned.scalar_one_or_none() is None:
                return False, "missing", set()
            if desired:
                found = await db.execute(
                    select(User.id).where(
                        User.id.in_(desired),
                        User.organization_id == org_id,
                    )
                )
                found_ids = {int(row[0]) for row in found.all()}
                if found_ids != desired:
                    return False, "not_in_org", set()
            current = await db.execute(select(DiagramShare).where(DiagramShare.diagram_id == diagram_id))
            rows = list(current.scalars().all())
            current_ids = {int(row.grantee_user_id) for row in rows}
            _added, removed = share_membership_delta(current_ids, desired)
            for row in rows:
                if int(row.grantee_user_id) in removed:
                    await db.delete(row)
            for user_id in _added:
                db.add(
                    DiagramShare(
                        diagram_id=diagram_id,
                        grantee_user_id=user_id,
                        shared_by_user_id=int(owner.id),
                    )
                )
            await db.commit()
            for user_id in removed:
                await drop_user_lease(diagram_id, user_id)
            return True, "", current_ids | desired
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.warning("[DiagramShare] replace failed diagram=%s: %s", diagram_id, exc)
            return False, "failed", set()


async def leave_share(user_id: int, diagram_id: str) -> bool:
    """Remove the caller's library row. Does not delete the diagram."""
    async with user_rls_session(user_id) as db:
        try:
            result = await db.execute(
                delete(DiagramShare).where(
                    DiagramShare.diagram_id == diagram_id,
                    DiagramShare.grantee_user_id == user_id,
                )
            )
            await db.commit()
            removed = result_rowcount(result) > 0
            if removed:
                await drop_user_lease(diagram_id, user_id)
            return removed
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.warning("[DiagramShare] leave failed diagram=%s: %s", diagram_id, exc)
            return False


async def set_share_pinned(user_id: int, diagram_id: str, pinned: bool) -> bool:
    """Pin or unpin the recipient's own library row."""
    async with user_rls_session(user_id) as db:
        try:
            result = await db.execute(
                select(DiagramShare).where(
                    DiagramShare.diagram_id == diagram_id,
                    DiagramShare.grantee_user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return False
            row.is_pinned = pinned
            await db.commit()
            return True
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.warning("[DiagramShare] pin failed diagram=%s: %s", diagram_id, exc)
            return False


async def set_share_folder(user_id: int, diagram_id: str, folder_id: Optional[str]) -> tuple[bool, str]:
    """Move the recipient's row into one of their folders."""
    async with user_rls_session(user_id) as db:
        try:
            result = await db.execute(
                select(DiagramShare).where(
                    DiagramShare.diagram_id == diagram_id,
                    DiagramShare.grantee_user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return False, "missing"
            if folder_id:
                folder = await db.execute(
                    select(DiagramFolder.id).where(
                        DiagramFolder.id == folder_id,
                        DiagramFolder.user_id == user_id,
                    )
                )
                if folder.scalar_one_or_none() is None:
                    return False, "folder"
            row.folder_id = folder_id
            await db.commit()
            return True, ""
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.warning("[DiagramShare] folder failed diagram=%s: %s", diagram_id, exc)
            return False, "failed"


async def current_grantee_ids(owner: User, diagram_id: str) -> Optional[set[int]]:
    """Grant ids for the share dialog, or None when the caller does not own it."""
    async with user_rls_session(int(owner.id), getattr(owner, "organization_id", None)) as db:
        try:
            owned = await db.execute(
                select(Diagram.id).where(
                    Diagram.id == diagram_id,
                    Diagram.user_id == owner.id,
                    Diagram.is_deleted.is_(False),
                )
            )
            if owned.scalar_one_or_none() is None:
                return None
            result = await db.execute(select(DiagramShare.grantee_user_id).where(DiagramShare.diagram_id == diagram_id))
            return {int(row[0]) for row in result.all()}
        except DATABASE_ERRORS as exc:
            logger.warning("[DiagramShare] candidates failed diagram=%s: %s", diagram_id, exc)
            return None
