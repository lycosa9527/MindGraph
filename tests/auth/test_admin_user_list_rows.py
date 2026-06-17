"""Paid-benefit fields on admin user list rows."""

from datetime import UTC, datetime

from models.domain.auth import Organization, User
from services.auth.admin_user_list_rows import (
    build_admin_user_detail_payload,
    build_admin_user_list_row,
)
from utils.auth.school_tier_defs import SCHOOL_TIER_TRIAL


def _user(org_id: int | None = 1) -> User:
    """User."""
    user = User()
    user.id = 1
    user.phone = "13800138000"
    user.name = "Test"
    user.role = "teacher"
    user.organization_id = org_id
    user.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    user.locked_until = None
    return user


def _org(expires_at: datetime | None) -> Organization:
    """Org."""
    org = Organization()
    org.id = 1
    org.code = "SCH-001"
    org.name = "Demo School"
    org.expires_at = expires_at
    return org


def test_list_row_includes_effective_school_tier():
    """Test list row includes effective school tier."""
    org = _org(None)
    org.school_tier = "standard"
    row = build_admin_user_list_row(
        _user(),
        org,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        0,
        {"expires_at": None, "permanent": False},
    )
    assert row["school_tier"] == "standard"


def test_list_row_trial_tier_for_trial_org():
    """Test list row trial tier for trial org."""
    org = _org(None)
    org.school_tier = SCHOOL_TIER_TRIAL
    row = build_admin_user_list_row(
        _user(),
        org,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        0,
        {"expires_at": None, "permanent": False},
    )
    assert row["school_tier"] == SCHOOL_TIER_TRIAL


def test_paid_benefit_uses_organization_expires_at():
    """Test paid benefit uses organization expires at."""
    expires = datetime(2026, 6, 1, 12, 0, 0)
    row = build_admin_user_list_row(
        _user(),
        _org(expires),
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        0,
        {"expires_at": None, "permanent": False},
    )
    assert row["paid_benefit_permanent"] is False
    assert row["paid_benefit_expires_at"] is not None
    assert "2026" in row["paid_benefit_expires_at"]


def test_paid_benefit_organization_without_expiry_is_permanent():
    """Test paid benefit organization without expiry is permanent."""
    row = build_admin_user_list_row(
        _user(),
        _org(None),
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        0,
        {"expires_at": None, "permanent": False},
    )
    assert row["paid_benefit_permanent"] is True
    assert row["paid_benefit_expires_at"] is None


def test_user_detail_payload_includes_email_and_diagram_remaining():
    """Test user detail payload includes email and diagram remaining."""
    org = _org(None)
    org.school_tier = "trial"
    user = _user()
    user.email = "teacher@example.com"
    payload = build_admin_user_detail_payload(user, org, diagram_count=3)
    assert payload["email"] == "teacher@example.com"
    assert payload["diagram_quota_max"] == 20
    assert payload["diagram_remaining"] == 17
    assert payload["school_tier"] == SCHOOL_TIER_TRIAL


def test_paid_tier_user_detail_has_unlimited_diagram_quota():
    """Test paid tier user detail has unlimited diagram quota."""
    org = _org(None)
    org.school_tier = "standard"
    user = _user()
    payload = build_admin_user_detail_payload(user, org, diagram_count=50)
    assert payload["diagram_quota_max"] == 0
    assert payload["diagram_remaining"] == 0


def test_paid_benefit_without_organization_uses_market():
    """Test paid benefit without organization uses market."""
    market_expires = datetime(2025, 12, 31, 0, 0, 0)
    row = build_admin_user_list_row(
        _user(org_id=None),
        None,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        0,
        {"expires_at": market_expires, "permanent": False},
    )
    assert row["paid_benefit_permanent"] is False
    assert row["paid_benefit_expires_at"] is not None
