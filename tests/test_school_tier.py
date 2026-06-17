"""Tests for organization school tier limits."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models.domain.auth import Organization
from models.domain.messages import Messages
from services.redis.cache.redis_org_cache import OrganizationCache
from tests.typing_helpers import as_organization, as_user
from utils.auth.school_tier import (
    DEFAULT_SCHOOL_TIER,
    SCHOOL_TIER_LITE,
    SCHOOL_TIER_PROFESSIONAL,
    SCHOOL_TIER_STANDARD,
    SCHOOL_TIER_TRIAL,
    TIER_FEATURE_API_TOKEN,
    TIER_FEATURE_ONLINE_COLLAB,
    apply_extra_member_seats_on_update,
    apply_school_tier_on_create,
    apply_school_tier_on_update,
    assert_organization_has_member_capacity,
    assert_organization_tier_allows_current_members,
    clear_extra_member_seats_if_trial,
    diagram_limit_reached_message,
    diagram_storage_limit_bytes_for_org,
    extra_member_seats_for_org,
    format_diagram_save_limit_error,
    is_unlimited_member_limit,
    manager_limit_for_org,
    max_diagrams_for_tier,
    max_diagrams_for_user,
    member_limit_for_org,
    normalize_school_tier,
    parse_diagram_save_limit_error,
    school_tier_allows_feature,
    school_tier_features_payload,
    school_tier_list_fields,
    user_has_school_tier_feature,
)
from utils.auth.school_tier_defs import EXTRA_MEMBER_SEATS_MAX


class _FakeOrg:
    """_FakeOrg helper."""

    def __init__(self, school_tier=None, extra_member_seats=0):
        """init  ."""
        self.school_tier = school_tier
        self.extra_member_seats = extra_member_seats
        self.id = 1
        self.expires_at = None
        self.code = ""
        self.name = ""
        self.invitation_code = ""
        self.is_active = True


def _org(school_tier=None, extra_member_seats=0, **attrs: object) -> Organization:
    """Org."""
    fake = _FakeOrg(school_tier, extra_member_seats)
    for key, value in attrs.items():
        setattr(fake, key, value)
    return cast(Organization, fake)


def test_normalize_school_tier_defaults_to_trial():
    """Test normalize school tier defaults to trial."""
    assert normalize_school_tier(None) == DEFAULT_SCHOOL_TIER
    assert normalize_school_tier("unknown") == DEFAULT_SCHOOL_TIER
    assert DEFAULT_SCHOOL_TIER == SCHOOL_TIER_TRIAL
    assert normalize_school_tier("STANDARD") == SCHOOL_TIER_STANDARD
    assert normalize_school_tier("LITE") == SCHOOL_TIER_LITE
    assert normalize_school_tier("TRIAL") == SCHOOL_TIER_TRIAL


def test_member_and_storage_limits_by_tier():
    """Test member and storage limits by tier."""
    trial = _org(SCHOOL_TIER_TRIAL)
    lite = _org(SCHOOL_TIER_LITE)
    standard = _org(SCHOOL_TIER_STANDARD)
    professional = _org(SCHOOL_TIER_PROFESSIONAL)

    assert is_unlimited_member_limit(member_limit_for_org(trial))
    assert member_limit_for_org(trial) == 0
    assert member_limit_for_org(lite) == 50
    assert member_limit_for_org(standard) == 120
    assert member_limit_for_org(professional) == 200

    assert manager_limit_for_org(trial) == 0
    assert manager_limit_for_org(lite) == 1
    assert manager_limit_for_org(standard) == 3
    assert manager_limit_for_org(professional) == 5

    assert max_diagrams_for_tier(SCHOOL_TIER_TRIAL) == 20
    assert max_diagrams_for_tier(SCHOOL_TIER_LITE) == 0
    assert max_diagrams_for_tier(SCHOOL_TIER_PROFESSIONAL) == 0

    assert diagram_storage_limit_bytes_for_org(lite, 10) == 10 * 1024**3
    assert diagram_storage_limit_bytes_for_org(trial, 10) == 10 * 1024**3
    assert diagram_storage_limit_bytes_for_org(standard, 25) == 50 * 1024**3
    assert diagram_storage_limit_bytes_for_org(professional, 4) == 20 * 1024**3


@pytest.mark.asyncio
async def test_trial_tier_allows_unlimited_members_on_downgrade_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test trial tier allows unlimited members on downgrade check."""
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_TRIAL)
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 500

    monkeypatch.setattr(
        "utils.auth.school_tier.member_count_for_org",
        _count,
    )

    await assert_organization_tier_allows_current_members(db, as_organization(org), "en")


def test_school_tier_list_fields():
    """Test school tier list fields."""
    trial_fields = school_tier_list_fields(_org(SCHOOL_TIER_TRIAL), 10)
    assert trial_fields["school_tier"] == SCHOOL_TIER_TRIAL
    assert trial_fields["school_tier_member_limit"] == 0
    assert trial_fields["extra_member_seats"] == 0
    assert trial_fields["member_limit_effective"] == 0
    assert trial_fields["school_tier_manager_limit"] == 0
    assert trial_fields["school_tier_features"]["online_collab"] is False

    fields = school_tier_list_fields(_org(SCHOOL_TIER_STANDARD), 25)
    assert fields["school_tier"] == SCHOOL_TIER_STANDARD
    assert fields["school_tier_member_limit"] == 120
    assert fields["extra_member_seats"] == 0
    assert fields["member_limit_effective"] == 120
    assert fields["school_tier_manager_limit"] == 3
    assert fields["school_tier_diagram_storage_bytes_per_member"] == 2 * 1024**3
    assert fields["school_tier_diagram_storage_bytes"] == 50 * 1024**3
    assert fields["school_tier_features"]["online_collab"] is True

    lite_extra = school_tier_list_fields(_org(SCHOOL_TIER_LITE, extra_member_seats=10), 5)
    assert lite_extra["extra_member_seats"] == 10
    assert lite_extra["member_limit_effective"] == 60


def test_member_limit_with_extra_seats():
    """Test member limit with extra seats."""
    lite = _org(SCHOOL_TIER_LITE, extra_member_seats=10)
    assert member_limit_for_org(lite) == 60
    assert extra_member_seats_for_org(lite) == 10

    standard = _org(SCHOOL_TIER_STANDARD, extra_member_seats=50)
    assert member_limit_for_org(standard) == 170

    trial = _org(SCHOOL_TIER_TRIAL, extra_member_seats=50)
    assert member_limit_for_org(trial) == 0
    assert is_unlimited_member_limit(member_limit_for_org(trial))


def test_member_limit_ignores_extra_when_subscription_expired():
    """Test member limit ignores extra when subscription expired."""
    expired_lite = _org(SCHOOL_TIER_LITE, extra_member_seats=10)
    expired_lite.expires_at = datetime.now(UTC) - timedelta(days=1)
    assert is_unlimited_member_limit(member_limit_for_org(expired_lite))


def test_apply_extra_member_seats_on_update():
    """Test apply extra member seats on update."""
    org = _org(SCHOOL_TIER_LITE)
    apply_extra_member_seats_on_update(org, {"extra_member_seats": 25}, "en")
    assert org.extra_member_seats == 25

    apply_extra_member_seats_on_update(org, {"extra_member_seats": "100"}, "en")
    assert org.extra_member_seats == 100


def test_apply_extra_member_seats_on_update_rejects_invalid():
    """Test apply extra member seats on update rejects invalid."""
    org = _org(SCHOOL_TIER_LITE)
    with pytest.raises(HTTPException) as exc_info:
        apply_extra_member_seats_on_update(org, {"extra_member_seats": -1}, "en")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        apply_extra_member_seats_on_update(
            org,
            {"extra_member_seats": EXTRA_MEMBER_SEATS_MAX + 1},
            "en",
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        apply_extra_member_seats_on_update(org, {"extra_member_seats": 1.5}, "en")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        apply_extra_member_seats_on_update(org, {"extra_member_seats": None}, "en")
    assert exc_info.value.status_code == 400


def test_clear_extra_member_seats_if_trial():
    """Test clear extra member seats if trial."""
    org = _org(SCHOOL_TIER_TRIAL, extra_member_seats=50)
    clear_extra_member_seats_if_trial(org)
    assert org.extra_member_seats == 0

    paid = _org(SCHOOL_TIER_LITE, extra_member_seats=10)
    clear_extra_member_seats_if_trial(paid)
    assert paid.extra_member_seats == 10


@pytest.mark.asyncio
async def test_assert_organization_tier_allows_current_members_with_extra_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test assert organization tier allows current members with extra seats."""
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_LITE, extra_member_seats=10)
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 55

    monkeypatch.setattr(
        "utils.auth.school_tier.member_count_for_org",
        _count,
    )

    await assert_organization_tier_allows_current_members(db, as_organization(org), "en")

    org.extra_member_seats = 0
    with pytest.raises(HTTPException) as exc_info:
        await assert_organization_tier_allows_current_members(db, as_organization(org), "en")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_assert_organization_has_member_capacity_respects_extra_seats() -> None:
    """Test assert organization has member capacity respects extra seats."""
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_LITE, extra_member_seats=10)
    db = AsyncMock()

    async def _count_59(_stmt):
        result = AsyncMock()
        result.scalar_one = lambda: 59
        return result

    db.execute = _count_59
    await assert_organization_has_member_capacity(db, as_organization(org), "en")

    async def _count_60(_stmt):
        result = AsyncMock()
        result.scalar_one = lambda: 60
        return result

    db.execute = _count_60
    with pytest.raises(HTTPException) as exc_info:
        await assert_organization_has_member_capacity(db, as_organization(org), "en")
    assert exc_info.value.status_code == 403


def test_school_tier_feature_gating():
    """Test school tier feature gating."""
    assert school_tier_allows_feature(SCHOOL_TIER_TRIAL, TIER_FEATURE_ONLINE_COLLAB) is False
    assert school_tier_allows_feature(SCHOOL_TIER_LITE, TIER_FEATURE_ONLINE_COLLAB) is False
    assert school_tier_allows_feature(SCHOOL_TIER_STANDARD, TIER_FEATURE_ONLINE_COLLAB) is True
    assert school_tier_allows_feature(SCHOOL_TIER_PROFESSIONAL, TIER_FEATURE_ONLINE_COLLAB) is True
    lite_features = school_tier_features_payload(SCHOOL_TIER_LITE)
    assert lite_features["presentation_tools"] is False
    assert lite_features["chrome_extension"] is False
    assert lite_features["api_token"] is False
    trial_features = school_tier_features_payload(SCHOOL_TIER_TRIAL)
    assert trial_features["online_collab"] is False
    assert trial_features["api_token"] is False
    assert school_tier_allows_feature(SCHOOL_TIER_LITE, TIER_FEATURE_API_TOKEN) is False
    assert school_tier_allows_feature(SCHOOL_TIER_STANDARD, TIER_FEATURE_API_TOKEN) is True


@pytest.mark.asyncio
async def test_assert_organization_tier_allows_current_members_rejects_over_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test assert organization tier allows current members rejects over cap."""
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_LITE)
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 60

    monkeypatch.setattr(
        "utils.auth.school_tier.member_count_for_org",
        _count,
    )

    with pytest.raises(HTTPException) as exc_info:
        await assert_organization_tier_allows_current_members(db, as_organization(org), "en")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_assert_organization_tier_allows_current_members_allows_within_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test assert organization tier allows current members allows within cap."""
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_LITE)
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 50

    monkeypatch.setattr(
        "utils.auth.school_tier.member_count_for_org",
        _count,
    )

    await assert_organization_tier_allows_current_members(db, as_organization(org), "en")


def test_apply_school_tier_on_create_defaults_to_trial():
    """Test apply school tier on create defaults to trial."""
    org = _org()
    apply_school_tier_on_create(org, {})
    assert org.school_tier == SCHOOL_TIER_TRIAL


def test_apply_school_tier_on_create_ignores_explicit_tier_without_superadmin():
    """Test apply school tier on create ignores explicit tier without superadmin."""
    org = _org()
    apply_school_tier_on_create(org, {"school_tier": "professional"})
    assert org.school_tier == SCHOOL_TIER_TRIAL


def test_apply_school_tier_on_create_accepts_explicit_tier_for_superadmin():
    """Test apply school tier on create accepts explicit tier for superadmin."""
    org = _org()
    apply_school_tier_on_create(
        org,
        {"school_tier": "professional"},
        allow_explicit_tier=True,
    )
    assert org.school_tier == SCHOOL_TIER_PROFESSIONAL


@pytest.mark.asyncio
async def test_user_has_school_tier_feature_denied_when_org_missing(monkeypatch):
    """Test user has school tier feature denied when org missing."""
    user = SimpleNamespace(id=1, organization_id=99, role="teacher")

    async def _no_org(_db, _user):
        return None

    monkeypatch.setattr(
        "utils.auth.school_tier.is_superadmin",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "utils.auth.school_tier._organization_for_user",
        _no_org,
    )
    allowed = await user_has_school_tier_feature(AsyncMock(), as_user(user), TIER_FEATURE_ONLINE_COLLAB)
    assert allowed is False


@pytest.mark.asyncio
async def test_max_diagrams_for_user_uses_trial_cap_when_org_missing(monkeypatch):
    """Test max diagrams for user uses trial cap when org missing."""
    user = SimpleNamespace(id=1, organization_id=99, role="teacher")

    async def _no_org(_db, _user):
        return None

    monkeypatch.setattr(
        "utils.auth.school_tier._organization_for_user",
        _no_org,
    )
    cap = await max_diagrams_for_user(AsyncMock(), as_user(user))
    assert cap == max_diagrams_for_tier(SCHOOL_TIER_TRIAL)


def test_apply_school_tier_on_update_rejects_unknown_tier():
    """Test apply school tier on update rejects unknown tier."""
    org = _org(SCHOOL_TIER_TRIAL)
    with pytest.raises(HTTPException) as exc_info:
        apply_school_tier_on_update(org, {"school_tier": "enterprise"}, "en")
    assert exc_info.value.status_code == 400
    assert org.school_tier == SCHOOL_TIER_TRIAL


def test_redis_org_cache_roundtrips_extra_member_seats():
    """Test redis org cache roundtrips extra member seats."""
    cache = OrganizationCache()
    serialize_org = getattr(cache, "_serialize_org")
    deserialize_org = getattr(cache, "_deserialize_org")
    org = _org(
        SCHOOL_TIER_LITE,
        extra_member_seats=25,
        id=42,
        code="DEMO",
        name="Demo School",
        invitation_code="INVITE",
        is_active=True,
    )

    payload = serialize_org(org)
    assert payload["extra_member_seats"] == "25"

    restored = deserialize_org(cast(dict[bytes | str, bytes | str], payload))
    assert restored.extra_member_seats == 25

    legacy_payload = {key: value for key, value in payload.items() if key != "extra_member_seats"}
    legacy_restored = deserialize_org(cast(dict[bytes | str, bytes | str], legacy_payload))
    assert legacy_restored.extra_member_seats == 0


def test_diagram_save_limit_error_token():
    """Test diagram save limit error token."""
    token = format_diagram_save_limit_error(20)
    assert parse_diagram_save_limit_error(token) == 20
    assert parse_diagram_save_limit_error("other error") is None
    assert diagram_limit_reached_message("zh", 20) == Messages.error("diagram_limit_reached", "zh", 20)
