"""Tests for B2B org subscription expiry downgrade."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.auth.org_subscription import (
    effective_school_tier_for_org,
    is_org_subscription_expired,
)
from utils.auth.school_tier import SCHOOL_TIER_STANDARD, SCHOOL_TIER_TRIAL


def _org(*, tier: str, expires_at=None, is_active: bool = True):
    return SimpleNamespace(
        id=1,
        code="DEMO-001",
        name="Demo School",
        school_tier=tier,
        expires_at=expires_at,
        is_active=is_active,
        invitation_code="INV-001",
    )


def test_is_org_subscription_expired_false_when_no_expiry():
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=None)
    assert is_org_subscription_expired(org) is False


def test_is_org_subscription_expired_true_when_past():
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    assert is_org_subscription_expired(org) is True


def test_is_org_subscription_expired_false_when_future():
    future = datetime.now(UTC) + timedelta(days=30)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=future)
    assert is_org_subscription_expired(org) is False


def test_effective_school_tier_for_org_downgrades_expired_paid_tier():
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    assert effective_school_tier_for_org(org) == SCHOOL_TIER_TRIAL


def test_effective_school_tier_for_org_keeps_active_paid_tier():
    future = datetime.now(UTC) + timedelta(days=30)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=future)
    assert effective_school_tier_for_org(org) == SCHOOL_TIER_STANDARD


def test_effective_school_tier_for_org_keeps_trial_when_expired():
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_TRIAL, expires_at=past)
    assert effective_school_tier_for_org(org) == SCHOOL_TIER_TRIAL


@pytest.mark.asyncio
async def test_downgrade_expired_org_to_trial_persists_trial():
    past = datetime.now(UTC) - timedelta(days=1)
    db_org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    db_org.code = "DEMO-001"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_org
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    class _SessionCtx:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, *_args):
            return False

    with patch("utils.auth.org_subscription.system_rls_session", return_value=_SessionCtx()):
        with patch("utils.auth.org_subscription._org_cache", None):
            from utils.auth.org_subscription import downgrade_expired_org_to_trial

            updated = await downgrade_expired_org_to_trial(1)

    assert updated is not None
    assert updated.school_tier == SCHOOL_TIER_TRIAL
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(db_org)
