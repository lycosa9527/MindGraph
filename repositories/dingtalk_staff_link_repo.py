"""Repository for dingtalk_staff_links."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.dingtalk_staff_link import DingtalkStaffLink
from services.auth.dingtalk_bind_constants import BIND_ERROR_INTERNAL, BIND_ERROR_STAFF_TAKEN
from services.utils.typing_helpers import result_rowcount


@dataclass(frozen=True)
class StaffLinkClaimResult:
    """Outcome of a universal QR bind claim."""

    ok: bool
    error_code: str = ""


class DingtalkStaffLinkRepository:
    """Persistence for DingTalk staff to MindGraph user links."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_staff(
        self,
        organization_id: int,
        dingtalk_staff_id: str,
    ) -> Optional[DingtalkStaffLink]:
        """Return link for org + staff id."""
        staff = (dingtalk_staff_id or "").strip()[:128]
        if not staff:
            return None
        stmt = select(DingtalkStaffLink).where(
            DingtalkStaffLink.organization_id == int(organization_id),
            DingtalkStaffLink.dingtalk_staff_id == staff,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_for_user(
        self,
        organization_id: int,
        user_id: int,
    ) -> Optional[DingtalkStaffLink]:
        """Return the user's link in this org."""
        stmt = (
            select(DingtalkStaffLink)
            .where(
                DingtalkStaffLink.organization_id == int(organization_id),
                DingtalkStaffLink.user_id == int(user_id),
            )
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def map_for_users(
        self,
        organization_id: int,
        user_ids: list[int],
    ) -> dict[int, DingtalkStaffLink]:
        """Return user_id -> link for many users in one org."""
        if not user_ids:
            return {}
        uid_set = {int(uid) for uid in user_ids if int(uid) > 0}
        if not uid_set:
            return {}
        stmt = select(DingtalkStaffLink).where(
            DingtalkStaffLink.organization_id == int(organization_id),
            DingtalkStaffLink.user_id.in_(uid_set),
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return {int(row.user_id): row for row in rows}

    async def map_for_users_all_orgs(
        self,
        user_ids: list[int],
    ) -> dict[tuple[int, int], DingtalkStaffLink]:
        """Return (organization_id, user_id) -> link for cross-org export."""
        if not user_ids:
            return {}
        uid_set = {int(uid) for uid in user_ids if int(uid) > 0}
        if not uid_set:
            return {}
        stmt = select(DingtalkStaffLink).where(DingtalkStaffLink.user_id.in_(uid_set))
        rows = (await self._db.execute(stmt)).scalars().all()
        return {(int(row.organization_id), int(row.user_id)): row for row in rows}

    async def claim_staff_link(
        self,
        *,
        organization_id: int,
        dingtalk_staff_id: str,
        user_id: int,
        linked_via: str = "qr_bind",
    ) -> StaffLinkClaimResult:
        """
        Link one DingTalk staff id to one MindGraph user within an org.

        Replaces the user's previous staff link when they bind a different account.
        Rejects when the staff id is already linked to a different user.
        """
        org_id = int(organization_id)
        uid = int(user_id)
        staff = (dingtalk_staff_id or "").strip()[:128]
        if not staff:
            return StaffLinkClaimResult(ok=False, error_code=BIND_ERROR_INTERNAL)

        staff_row = await self.get_by_staff(org_id, staff)
        if staff_row is not None and int(staff_row.user_id) != uid:
            return StaffLinkClaimResult(ok=False, error_code=BIND_ERROR_STAFF_TAKEN)

        user_row = await self.get_for_user(org_id, uid)
        if user_row is not None and user_row.dingtalk_staff_id == staff:
            user_row.linked_via = linked_via[:32]
            user_row.linked_at = datetime.now(UTC)
            await self._db.flush()
            return StaffLinkClaimResult(ok=True)

        if user_row is not None and user_row.dingtalk_staff_id != staff:
            await self._db.delete(user_row)
            await self._db.flush()

        if staff_row is not None:
            staff_row.user_id = uid
            staff_row.linked_via = linked_via[:32]
            staff_row.linked_at = datetime.now(UTC)
            await self._db.flush()
            return StaffLinkClaimResult(ok=True)

        self._db.add(
            DingtalkStaffLink(
                organization_id=org_id,
                dingtalk_staff_id=staff,
                user_id=uid,
                linked_via=linked_via[:32],
            )
        )
        await self._db.flush()
        return StaffLinkClaimResult(ok=True)

    async def upsert_link(
        self,
        *,
        organization_id: int,
        dingtalk_staff_id: str,
        user_id: int,
        linked_via: str = "qr_bind",
    ) -> DingtalkStaffLink:
        """Create or update staff link using universal claim rules."""
        result = await self.claim_staff_link(
            organization_id=organization_id,
            dingtalk_staff_id=dingtalk_staff_id,
            user_id=user_id,
            linked_via=linked_via,
        )
        if not result.ok:
            raise ValueError(result.error_code)
        row = await self.get_for_user(int(organization_id), int(user_id))
        if row is None:
            row = await self.get_by_staff(int(organization_id), dingtalk_staff_id)
        if row is None:
            raise ValueError("link_missing_after_claim")
        return row

    async def resolve_user_id_for_staff(
        self,
        organization_id: int,
        dingtalk_staff_id: str,
    ) -> Optional[int]:
        """Return linked MindGraph user id or None."""
        row = await self.get_by_staff(organization_id, dingtalk_staff_id)
        if row is None:
            return None
        return int(row.user_id)

    async def delete_for_user(self, organization_id: int, user_id: int) -> bool:
        """Remove the user's DingTalk link in this org. Returns True if a row was deleted."""
        stmt = delete(DingtalkStaffLink).where(
            DingtalkStaffLink.organization_id == int(organization_id),
            DingtalkStaffLink.user_id == int(user_id),
        )
        result = await self._db.execute(stmt)
        await self._db.flush()
        return result_rowcount(result) > 0
