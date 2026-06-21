"""Tests for thinking coin eligibility rules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.auth.thinking_coin import eligibility as eligibility_mod
from tests.typing_helpers import as_organization, as_user


def _user(role: str = "teacher", org_id: int | None = 1) -> object:
    return SimpleNamespace(id=42, role=role, organization_id=org_id)


def _org(school_tier: str | None = "trial") -> object:
    return SimpleNamespace(id=1, school_tier=school_tier, expires_at=None)


def test_feature_flag_off_disables_eligibility(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wallet hidden when FEATURE_THINKING_COINS is false."""
    monkeypatch.delenv("FEATURE_THINKING_COINS", raising=False)
    assert (
        eligibility_mod.user_eligible_for_thinking_coins(
            as_user(_user()),
            as_organization(_org()),
        )
        is False
    )


def test_trial_teacher_is_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    """B2B trial teachers qualify."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")
    assert (
        eligibility_mod.user_eligible_for_thinking_coins(
            as_user(_user("teacher")),
            as_organization(_org("trial")),
        )
        is True
    )


def test_trial_school_admin_is_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    """School admins on trial tier qualify."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")
    assert (
        eligibility_mod.user_eligible_for_thinking_coins(
            as_user(_user("school_admin")),
            as_organization(_org("trial")),
        )
        is True
    )


def test_lite_org_not_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paid school tiers bypass thinking coins."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")
    assert (
        eligibility_mod.user_eligible_for_thinking_coins(
            as_user(_user("teacher")),
            as_organization(_org("lite")),
        )
        is False
    )


def test_c2c_personal_trial_without_org_not_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    """C2C accounts without an org are not eligible."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")
    assert (
        eligibility_mod.user_eligible_for_thinking_coins(
            as_user(_user("personal_trial", None)),
            None,
        )
        is False
    )


def test_platform_superadmin_not_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Platform roles on a trial org still do not earn/spend trial coins."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")
    assert (
        eligibility_mod.user_eligible_for_thinking_coins(
            as_user(_user("superadmin")),
            as_organization(_org("trial")),
        )
        is False
    )
