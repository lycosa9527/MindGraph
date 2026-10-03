"""School tier feature access is not denied for trial or lite organizations."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.typing_helpers import as_user
from utils.auth.school_tier import (
    TIER_FEATURE_API_TOKEN,
    TIER_FEATURE_ONLINE_COLLAB,
    assert_user_has_school_tier_feature,
)


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    """Make user."""
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    user.phone = "13800000001"
    return user


@pytest.fixture(name="trial_org_user")
def fixture_trial_org_user(monkeypatch: pytest.MonkeyPatch):
    """Fixture trial org user."""
    user = _make_user("teacher", organization_id=8)

    async def _trial_org(_db, _user):
        return SimpleNamespace(id=8, school_tier="trial")

    monkeypatch.setattr(
        "utils.auth.school_tier.is_superadmin",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "utils.auth.school_tier._organization_for_user",
        _trial_org,
    )
    return user


@pytest.fixture(name="lite_org_user")
def fixture_lite_org_user(monkeypatch: pytest.MonkeyPatch):
    """Fixture lite org user."""
    user = _make_user("teacher", organization_id=7)

    async def _lite_org(_db, _user):
        return SimpleNamespace(id=7, school_tier="lite")

    monkeypatch.setattr(
        "utils.auth.school_tier.is_superadmin",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "utils.auth.school_tier._organization_for_user",
        _lite_org,
    )
    return user


@pytest.mark.asyncio
async def test_lite_tier_allows_online_collab(lite_org_user: SimpleNamespace) -> None:
    """Lite schools can start online collaboration."""
    await assert_user_has_school_tier_feature(
        AsyncMock(),
        as_user(lite_org_user),
        TIER_FEATURE_ONLINE_COLLAB,
        "en",
    )


@pytest.mark.asyncio
async def test_lite_tier_allows_api_token(lite_org_user: SimpleNamespace) -> None:
    """Lite schools can mint an API token."""
    await assert_user_has_school_tier_feature(
        AsyncMock(),
        as_user(lite_org_user),
        TIER_FEATURE_API_TOKEN,
        "en",
    )


@pytest.mark.asyncio
async def test_trial_tier_allows_online_collab(trial_org_user: SimpleNamespace) -> None:
    """Trial schools can start online collaboration."""
    await assert_user_has_school_tier_feature(
        AsyncMock(),
        as_user(trial_org_user),
        TIER_FEATURE_ONLINE_COLLAB,
        "en",
    )


@pytest.mark.asyncio
async def test_trial_tier_allows_api_token(trial_org_user: SimpleNamespace) -> None:
    """Trial schools can mint an API token."""
    await assert_user_has_school_tier_feature(
        AsyncMock(),
        as_user(trial_org_user),
        TIER_FEATURE_API_TOKEN,
        "en",
    )
