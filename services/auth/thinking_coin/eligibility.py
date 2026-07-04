"""Eligibility for the thinking coin wallet."""

from __future__ import annotations

from models.domain.auth import Organization, User
from utils.auth.school_tier_defs import SCHOOL_TIER_TRIAL
from utils.auth.school_tier_effective import effective_school_tier_for_org
from utils.auth.thinking_coin_config import feature_thinking_coins_enabled


def user_eligible_for_thinking_coins(user: User | None, org: Organization | None) -> bool:
    """Any org member whose school is on trial tier when feature flag is on."""
    if not feature_thinking_coins_enabled():
        return False
    if user is None or org is None:
        return False
    org_id = getattr(user, "organization_id", None)
    if org_id is None:
        return False
    if int(org_id) != int(getattr(org, "id", 0) or 0):
        return False
    return effective_school_tier_for_org(org) == SCHOOL_TIER_TRIAL
