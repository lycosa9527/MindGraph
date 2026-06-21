"""Eligibility for the thinking coin wallet."""

from __future__ import annotations

from models.domain.auth import Organization, User
from utils.auth.role_constants import ROLE_SCHOOL_ADMIN, ROLE_TEACHER
from utils.auth.roles import role_in
from utils.auth.school_tier_defs import SCHOOL_TIER_TRIAL
from utils.auth.school_tier_effective import effective_school_tier_for_org
from utils.auth.thinking_coin_config import feature_thinking_coins_enabled


def user_eligible_for_thinking_coins(user: User | None, org: Organization | None) -> bool:
    """Trial-org teachers and school admins when feature flag is on."""
    if not feature_thinking_coins_enabled():
        return False
    if user is None or org is None:
        return False
    if effective_school_tier_for_org(org) != SCHOOL_TIER_TRIAL:
        return False
    return role_in(user, frozenset({ROLE_TEACHER, ROLE_SCHOOL_ADMIN}))
