"""Visibility rules for MindMate collab join authorization."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.features.mindmate_collab.visibility import user_may_join_mindmate_collab
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from utils.auth.role_constants import ROLE_EXPERT, ROLE_SUPERADMIN, ROLE_TEACHER


def _mock_db(users: list[tuple[int, str, int | None]]) -> AsyncMock:
    rows = [SimpleNamespace(id=uid, role=role, organization_id=org) for uid, role, org in users]
    result = MagicMock()
    result.all.return_value = rows
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_network_visibility_allows_any_joiner() -> None:
    """Network rooms allow join without org membership checks."""
    db = _mock_db([(2, ROLE_TEACHER, 99)])
    allowed = await user_may_join_mindmate_collab(
        db,
        visibility=ONLINE_COLLAB_VISIBILITY_NETWORK,
        owner_user_id=1,
        owner_org_id=1,
        joiner_id=2,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_same_org_teacher_may_join_org_room() -> None:
    """Teachers in the host org may join org-visible rooms."""
    db = _mock_db(
        [
            (1, ROLE_TEACHER, 10),
            (2, ROLE_TEACHER, 10),
        ]
    )
    allowed = await user_may_join_mindmate_collab(
        db,
        visibility=ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        owner_user_id=1,
        owner_org_id=10,
        joiner_id=2,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_cross_org_teacher_denied_for_org_room() -> None:
    """Teachers outside the host org cannot join org-visible rooms."""
    db = _mock_db(
        [
            (1, ROLE_TEACHER, 10),
            (2, ROLE_TEACHER, 20),
        ]
    )
    allowed = await user_may_join_mindmate_collab(
        db,
        visibility=ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        owner_user_id=1,
        owner_org_id=10,
        joiner_id=2,
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_expert_may_join_any_org_room() -> None:
    """Expert role bypasses org isolation for org-visible rooms."""
    db = _mock_db(
        [
            (1, ROLE_TEACHER, 10),
            (2, ROLE_EXPERT, 20),
        ]
    )
    allowed = await user_may_join_mindmate_collab(
        db,
        visibility=ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        owner_user_id=1,
        owner_org_id=10,
        joiner_id=2,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_superadmin_may_join_any_org_room() -> None:
    """Superadmin role bypasses org isolation for org-visible rooms."""
    db = _mock_db(
        [
            (1, ROLE_TEACHER, 10),
            (2, ROLE_SUPERADMIN, None),
        ]
    )
    allowed = await user_may_join_mindmate_collab(
        db,
        visibility=ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        owner_user_id=1,
        owner_org_id=10,
        joiner_id=2,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_owner_always_allowed() -> None:
    """Room host may always re-enter without a DB lookup."""
    db = _mock_db([])
    allowed = await user_may_join_mindmate_collab(
        db,
        visibility=ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        owner_user_id=5,
        owner_org_id=10,
        joiner_id=5,
    )
    assert allowed is True
