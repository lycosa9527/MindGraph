"""Tests for organization school tier limits."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from utils.auth.school_tier import (
    DEFAULT_SCHOOL_TIER,
    SCHOOL_TIER_LITE,
    SCHOOL_TIER_PROFESSIONAL,
    SCHOOL_TIER_STANDARD,
    TIER_FEATURE_API_TOKEN,
    TIER_FEATURE_ONLINE_COLLAB,
    assert_organization_tier_allows_current_members,
    diagram_storage_limit_bytes_for_org,
    manager_limit_for_org,
    member_limit_for_org,
    normalize_school_tier,
    school_tier_allows_feature,
    school_tier_features_payload,
    school_tier_list_fields,
)


class _FakeOrg:
    def __init__(self, school_tier=None):
        self.school_tier = school_tier


def test_normalize_school_tier_defaults_to_standard():
    assert normalize_school_tier(None) == DEFAULT_SCHOOL_TIER
    assert normalize_school_tier("unknown") == DEFAULT_SCHOOL_TIER
    assert DEFAULT_SCHOOL_TIER == SCHOOL_TIER_STANDARD
    assert normalize_school_tier("STANDARD") == SCHOOL_TIER_STANDARD
    assert normalize_school_tier("LITE") == SCHOOL_TIER_LITE


def test_member_and_storage_limits_by_tier():
    lite = _FakeOrg(SCHOOL_TIER_LITE)
    standard = _FakeOrg(SCHOOL_TIER_STANDARD)
    professional = _FakeOrg(SCHOOL_TIER_PROFESSIONAL)

    assert member_limit_for_org(lite) == 50
    assert member_limit_for_org(standard) == 120
    assert member_limit_for_org(professional) == 200

    assert manager_limit_for_org(lite) == 1
    assert manager_limit_for_org(standard) == 3
    assert manager_limit_for_org(professional) == 5

    assert diagram_storage_limit_bytes_for_org(lite, 10) == 10 * 1024**3
    assert diagram_storage_limit_bytes_for_org(standard, 25) == 50 * 1024**3
    assert diagram_storage_limit_bytes_for_org(professional, 4) == 20 * 1024**3


def test_school_tier_list_fields():
    fields = school_tier_list_fields(_FakeOrg(SCHOOL_TIER_STANDARD), 25)
    assert fields["school_tier"] == SCHOOL_TIER_STANDARD
    assert fields["school_tier_member_limit"] == 120
    assert fields["school_tier_manager_limit"] == 3
    assert fields["school_tier_diagram_storage_bytes_per_member"] == 2 * 1024**3
    assert fields["school_tier_diagram_storage_bytes"] == 50 * 1024**3
    assert fields["school_tier_features"]["online_collab"] is True


def test_school_tier_feature_gating():
    assert school_tier_allows_feature(SCHOOL_TIER_LITE, TIER_FEATURE_ONLINE_COLLAB) is False
    assert school_tier_allows_feature(SCHOOL_TIER_STANDARD, TIER_FEATURE_ONLINE_COLLAB) is True
    assert school_tier_allows_feature(SCHOOL_TIER_PROFESSIONAL, TIER_FEATURE_ONLINE_COLLAB) is True
    lite_features = school_tier_features_payload(SCHOOL_TIER_LITE)
    assert lite_features["presentation_tools"] is False
    assert lite_features["chrome_extension"] is False
    assert lite_features["api_token"] is False
    assert school_tier_allows_feature(SCHOOL_TIER_LITE, TIER_FEATURE_API_TOKEN) is False
    assert school_tier_allows_feature(SCHOOL_TIER_STANDARD, TIER_FEATURE_API_TOKEN) is True


@pytest.mark.asyncio
async def test_assert_organization_tier_allows_current_members_rejects_over_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_LITE)
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 60

    monkeypatch.setattr(
        "utils.auth.school_tier.member_count_for_org",
        _count,
    )

    with pytest.raises(HTTPException) as exc_info:
        await assert_organization_tier_allows_current_members(db, org, "en")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_assert_organization_tier_allows_current_members_allows_within_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = SimpleNamespace(id=1, school_tier=SCHOOL_TIER_LITE)
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 50

    monkeypatch.setattr(
        "utils.auth.school_tier.member_count_for_org",
        _count,
    )

    await assert_organization_tier_allows_current_members(db, org, "en")
