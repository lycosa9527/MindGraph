"""Tests for B2B org subscription expiry hard lockout."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import pytest

from models.domain.auth import Organization

from utils.auth.org_subscription import (
    ORG_SUBSCRIPTION_EXPIRED_CODE,
    downgrade_expired_org_to_trial,
    effective_school_tier_for_org,
    enforce_org_accessible_or_raise,
    is_org_subscription_expired,
    should_bypass_org_subscription_lock,
)
from utils.auth.school_tier import SCHOOL_TIER_LITE, SCHOOL_TIER_STANDARD, SCHOOL_TIER_TRIAL


def _error_detail_map(exc: HTTPException) -> dict[str, str]:
    """Read structured FastAPI detail as a string map."""
    raw = exc.detail
    if not isinstance(raw, dict):
        raise AssertionError(f"expected dict detail, got {type(raw)}")
    return {str(key): str(value) for key, value in raw.items()}


def _org(*, tier: str, expires_at=None, is_active: bool = True) -> Organization:
    """Org."""
    return cast(
        Organization,
        SimpleNamespace(
            id=1,
            code="DEMO-001",
            name="Demo School",
            school_tier=tier,
            expires_at=expires_at,
            is_active=is_active,
            invitation_code="INV-001",
        ),
    )


def test_is_org_subscription_expired_false_when_no_expiry():
    """Test is org subscription expired false when no expiry."""
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=None)
    assert is_org_subscription_expired(org) is False


def test_is_org_subscription_expired_true_when_past():
    """Test is org subscription expired true when past."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    assert is_org_subscription_expired(org) is True


def test_is_org_subscription_expired_false_when_future():
    """Test is org subscription expired false when future."""
    future = datetime.now(UTC) + timedelta(days=30)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=future)
    assert is_org_subscription_expired(org) is False


def test_effective_school_tier_for_org_downgrades_expired_paid_tier():
    """Test effective school tier for org downgrades expired paid tier."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    assert effective_school_tier_for_org(org) == SCHOOL_TIER_TRIAL


def test_effective_school_tier_for_org_keeps_active_paid_tier():
    """Test effective school tier for org keeps active paid tier."""
    future = datetime.now(UTC) + timedelta(days=30)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=future)
    assert effective_school_tier_for_org(org) == SCHOOL_TIER_STANDARD


def test_effective_school_tier_for_org_keeps_trial_when_expired():
    """Test effective school tier for org keeps trial when expired."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_TRIAL, expires_at=past)
    assert effective_school_tier_for_org(org) == SCHOOL_TIER_TRIAL


@pytest.mark.asyncio
async def test_downgrade_expired_org_to_trial_persists_trial():
    """Test downgrade expired org to trial persists trial."""
    past = datetime.now(UTC) - timedelta(days=1)
    db_org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    db_org.code = "DEMO-001"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_org
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    class _SessionCtx:
        async def __aenter__(self):
            """aenter  ."""
            return mock_db

        async def __aexit__(self, *_args):
            """aexit  ."""
            return False

    with patch("utils.auth.org_subscription_downgrade.system_rls_session", return_value=_SessionCtx()):
        with patch("utils.auth.org_subscription_downgrade._org_cache", None):
            updated = await downgrade_expired_org_to_trial(1)

    assert updated is not None
    assert updated.school_tier == SCHOOL_TIER_TRIAL
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(db_org)


@pytest.mark.asyncio
async def test_enforce_org_raises_when_paid_tier_expired():
    """Expired paid school product hard-locks teachers and school managers."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    with pytest.raises(HTTPException) as exc_info:
        await enforce_org_accessible_or_raise(org, "en")
    assert exc_info.value.status_code == 403
    detail = _error_detail_map(exc_info.value)
    assert detail["code"] == ORG_SUBSCRIPTION_EXPIRED_CODE
    assert "Demo School" in detail["message"]


@pytest.mark.asyncio
async def test_enforce_org_raises_when_trial_expired():
    """Trial schools with a past expires_at are also hard-locked."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_TRIAL, expires_at=past)
    with pytest.raises(HTTPException) as exc_info:
        await enforce_org_accessible_or_raise(org, "en")
    assert exc_info.value.status_code == 403
    assert _error_detail_map(exc_info.value)["code"] == ORG_SUBSCRIPTION_EXPIRED_CODE


@pytest.mark.asyncio
async def test_enforce_org_allows_future_expiry():
    """Active subscription remains accessible."""
    future = datetime.now(UTC) + timedelta(days=30)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=future)
    result = await enforce_org_accessible_or_raise(org, "en")
    assert result is org


@pytest.mark.asyncio
async def test_enforce_org_allows_no_expiry():
    """Schools without expires_at stay open."""
    org = _org(tier=SCHOOL_TIER_LITE, expires_at=None)
    result = await enforce_org_accessible_or_raise(org, "en")
    assert result is org


@pytest.mark.asyncio
async def test_enforce_org_platform_user_bypasses_expiry():
    """Platform admins can still sign in to renew an expired school."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    user = SimpleNamespace(role="superadmin")
    result = await enforce_org_accessible_or_raise(org, "en", user)
    assert result is org


@pytest.mark.asyncio
async def test_enforce_org_school_manager_is_locked_when_expired():
    """School managers are locked out with the rest of the school."""
    past = datetime.now(UTC) - timedelta(days=1)
    org = _org(tier=SCHOOL_TIER_STANDARD, expires_at=past)
    user = SimpleNamespace(role="school_admin")
    with pytest.raises(HTTPException) as exc_info:
        await enforce_org_accessible_or_raise(org, "en", user)
    assert exc_info.value.status_code == 403


def test_should_bypass_org_subscription_lock_platform_only():
    """Only platform-tier roles bypass the school product lockout."""
    assert should_bypass_org_subscription_lock(SimpleNamespace(role="superadmin")) is True
    assert should_bypass_org_subscription_lock(SimpleNamespace(role="school_admin")) is False
    assert should_bypass_org_subscription_lock(SimpleNamespace(role="teacher")) is False
    assert should_bypass_org_subscription_lock(None) is False
