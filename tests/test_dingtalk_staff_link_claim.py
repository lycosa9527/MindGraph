"""Tests for DingTalk staff link one-user-one-staff rules."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from services.auth.dingtalk_bind_constants import BIND_ERROR_STAFF_TAKEN


def _staff_row(*, org: int, staff: str, user: int, row_id: int = 1) -> MagicMock:
    row = MagicMock()
    row.id = row_id
    row.organization_id = org
    row.dingtalk_staff_id = staff
    row.user_id = user
    return row


@pytest.mark.asyncio
async def test_claim_staff_link_rejects_staff_bound_to_other_user() -> None:
    """Staff already linked to another MindGraph user is rejected."""
    db = AsyncMock()
    repo = DingtalkStaffLinkRepository(db)
    repo.get_by_staff = AsyncMock(return_value=_staff_row(org=5, staff="staffA", user=99))
    repo.get_for_user = AsyncMock(return_value=None)

    result = await repo.claim_staff_link(
        organization_id=5,
        dingtalk_staff_id="staffA",
        user_id=42,
    )

    assert result.ok is False
    assert result.error_code == BIND_ERROR_STAFF_TAKEN


@pytest.mark.asyncio
async def test_claim_staff_link_replaces_user_previous_staff() -> None:
    """User binding a new staff removes their old staff link."""
    db = AsyncMock()
    repo = DingtalkStaffLinkRepository(db)
    old_link = _staff_row(org=5, staff="staffOld", user=42, row_id=7)
    repo.get_by_staff = AsyncMock(return_value=None)
    repo.get_for_user = AsyncMock(return_value=old_link)
    db.delete = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    result = await repo.claim_staff_link(
        organization_id=5,
        dingtalk_staff_id="staffNew",
        user_id=42,
    )

    assert result.ok is True
    db.delete.assert_awaited_once_with(old_link)
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_claim_staff_link_idempotent_same_pair() -> None:
    """Re-scanning the same QR for the same staff succeeds."""
    db = AsyncMock()
    repo = DingtalkStaffLinkRepository(db)
    same = _staff_row(org=5, staff="staffA", user=42)
    repo.get_by_staff = AsyncMock(return_value=same)
    repo.get_for_user = AsyncMock(return_value=same)
    db.flush = AsyncMock()

    result = await repo.claim_staff_link(
        organization_id=5,
        dingtalk_staff_id="staffA",
        user_id=42,
    )

    assert result.ok is True
    db.delete.assert_not_called()
