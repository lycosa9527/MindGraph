"""Workshop Chat access: preview-org allowlist, not all school admins."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.domain.auth import User
from models.domain.feature_org_access import FeatureOrgAccessEntry
from tests.typing_helpers import as_user
from utils.auth.roles import can_access_workshop_chat, user_has_feature_access


def _user(*, role: str, organization_id: int | None, user_id: int = 10) -> User:
    """Build a typed user double for access checks."""
    return as_user(SimpleNamespace(id=user_id, role=role, organization_id=organization_id))


@pytest.fixture(name="workshop_preview_config")
def workshop_preview_config_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable Workshop Chat with preview org 5 and no DB grant map."""
    monkeypatch.setattr(
        "utils.auth.roles.config",
        SimpleNamespace(
            FEATURE_WORKSHOP_CHAT=True,
            WORKSHOP_CHAT_PREVIEW_ORG_IDS=frozenset({5}),
        ),
    )
    monkeypatch.setattr(
        "utils.auth.roles._get_feature_access_map_cached",
        AsyncMock(return_value=None),
    )


@pytest.mark.usefixtures("workshop_preview_config")
@pytest.mark.asyncio
async def test_org_five_teacher_can_access() -> None:
    """Teachers in the preview org may use Workshop Chat."""
    assert await can_access_workshop_chat(_user(role="teacher", organization_id=5))


@pytest.mark.usefixtures("workshop_preview_config")
@pytest.mark.asyncio
async def test_org_five_school_admin_can_access() -> None:
    """School admins in the preview org may use Workshop Chat."""
    assert await can_access_workshop_chat(_user(role="school_admin", organization_id=5))


@pytest.mark.usefixtures("workshop_preview_config")
@pytest.mark.asyncio
async def test_other_org_teacher_denied() -> None:
    """Teachers outside the preview org cannot see Workshop Chat."""
    assert not await can_access_workshop_chat(_user(role="teacher", organization_id=7))


@pytest.mark.usefixtures("workshop_preview_config")
@pytest.mark.asyncio
async def test_other_org_school_admin_denied() -> None:
    """School admins outside the preview org no longer get a free pass."""
    assert not await can_access_workshop_chat(_user(role="school_admin", organization_id=7))


@pytest.mark.usefixtures("workshop_preview_config")
@pytest.mark.asyncio
async def test_superadmin_can_access_without_org() -> None:
    """Platform superadmins keep access for operations."""
    assert await can_access_workshop_chat(_user(role="superadmin", organization_id=None))


@pytest.mark.asyncio
async def test_unrestricted_db_row_still_limited_to_preview_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wide-open Permissions row must not leak past the preview-org list."""
    monkeypatch.setattr(
        "utils.auth.roles.config",
        SimpleNamespace(
            FEATURE_WORKSHOP_CHAT=True,
            WORKSHOP_CHAT_PREVIEW_ORG_IDS=frozenset({5}),
        ),
    )
    monkeypatch.setattr(
        "utils.auth.roles._get_feature_access_map_cached",
        AsyncMock(
            return_value={
                "feature_workshop_chat": FeatureOrgAccessEntry(restrict=False),
            }
        ),
    )
    assert await user_has_feature_access(
        _user(role="teacher", organization_id=5),
        "feature_workshop_chat",
    )
    assert not await user_has_feature_access(
        _user(role="teacher", organization_id=7),
        "feature_workshop_chat",
    )


@pytest.mark.asyncio
async def test_flag_off_denies_preview_org(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preview-org membership does not override a disabled global flag."""
    monkeypatch.setattr(
        "utils.auth.roles.config",
        SimpleNamespace(
            FEATURE_WORKSHOP_CHAT=False,
            WORKSHOP_CHAT_PREVIEW_ORG_IDS=frozenset({5}),
        ),
    )
    monkeypatch.setattr(
        "utils.auth.roles._get_feature_access_map_cached",
        AsyncMock(return_value=None),
    )
    assert not await can_access_workshop_chat(_user(role="teacher", organization_id=5))
