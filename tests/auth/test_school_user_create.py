"""Unit tests for school dashboard member creation helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from services.auth.school_user_create import (
    MAX_BATCH_MEMBERS,
    SchoolMemberInput,
    assert_batch_member_capacity,
    normalize_school_member_phone,
    parse_school_member_batch,
    parse_school_member_input,
    try_parse_school_member_item,
    validate_school_member_phone,
)
from utils.auth.school_tier_defs import SCHOOL_TIER_LITE
from utils.auth.role_constants import ROLE_SCHOOL_ADMIN, ROLE_SUPERADMIN
from tests.typing_helpers import as_organization


def test_validate_school_member_phone_rejects_invalid() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_school_member_phone("123", "en")
    assert exc.value.status_code == 400


def test_normalize_school_member_phone_accepts_formatted_values() -> None:
    assert normalize_school_member_phone("+86 138-0013-8000") == "13800138000"
    assert normalize_school_member_phone("1.3800138000E+10") == "13800138000"
    assert normalize_school_member_phone("13800138000.0") == "13800138000"


def test_validate_school_member_phone_normalizes_before_checking() -> None:
    assert validate_school_member_phone("+86 138-0013-8000", "en") == "13800138000"


def test_parse_school_member_input_normalizes_phone_fields() -> None:
    member = parse_school_member_input(
        {"phone": "13812345678", "name": "  Zhang San  ", "role": "teacher"},
        "en",
    )
    assert member.phone == "13812345678"
    assert member.email is None
    assert member.name == "Zhang San"
    assert member.role == "teacher"


def test_parse_school_member_input_accepts_email() -> None:
    member = parse_school_member_input(
        {"email": "Teacher@Example.com", "name": "Alice", "role": "teacher"},
        "en",
    )
    assert member.phone is None
    assert member.email == "teacher@example.com"
    assert member.name == "Alice"


def test_try_parse_school_member_item_reports_invalid_phone_for_name() -> None:
    member, failure = try_parse_school_member_item(
        {"phone": "123", "name": "Alice"},
        "en",
    )
    assert member is None
    assert failure is not None
    assert "Alice" in failure.detail
    assert failure.name == "Alice"


def test_try_parse_school_member_item_reports_invalid_email_for_name() -> None:
    member, failure = try_parse_school_member_item(
        {"email": "not-an-email", "name": "Bob"},
        "en",
    )
    assert member is None
    assert failure is not None
    assert "Bob" in failure.detail


def test_parse_school_member_input_rejects_manager_role_for_school_admin_actor() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_school_member_input(
            {"phone": "13812345678", "name": "Manager", "role": ROLE_SCHOOL_ADMIN},
            "en",
            actor_role=ROLE_SCHOOL_ADMIN,
        )
    assert exc.value.status_code == 403


def test_parse_school_member_input_allows_manager_role_for_superadmin() -> None:
    member = parse_school_member_input(
        {"phone": "13812345679", "name": "Manager", "role": ROLE_SCHOOL_ADMIN},
        "en",
        actor_role=ROLE_SUPERADMIN,
    )
    assert member.role == ROLE_SCHOOL_ADMIN


def test_parse_school_member_batch_deduplicates_contacts() -> None:
    members, failed = parse_school_member_batch(
        [
            {"phone": "13812345678", "name": "Alice"},
            {"phone": "13812345678", "name": "Bob"},
            {"phone": "13812345679", "name": "Carol"},
        ],
        "en",
    )
    assert len(members) == 2
    assert members[0].phone == "13812345678"
    assert members[1].phone == "13812345679"
    assert not failed


def test_parse_school_member_batch_collects_invalid_rows() -> None:
    members, failed = parse_school_member_batch(
        [
            {"phone": "13812345678", "name": "Alice"},
            {"phone": "123", "name": "Bob"},
        ],
        "en",
    )
    assert len(members) == 1
    assert len(failed) == 1
    assert failed[0].name == "Bob"


def test_parse_school_member_batch_rejects_too_many_rows() -> None:
    payload = [{"phone": f"138{index:08d}", "name": f"User{index}"} for index in range(MAX_BATCH_MEMBERS + 1)]
    with pytest.raises(HTTPException) as exc:
        parse_school_member_batch(payload, "en")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_assert_batch_member_capacity_allows_extra_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = as_organization(type("Org", (), {"id": 1, "school_tier": SCHOOL_TIER_LITE, "extra_member_seats": 10})())
    members = [SchoolMemberInput(phone="13812345678", email=None, name="New", role="teacher")]
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 50

    monkeypatch.setattr(
        "services.auth.school_user_create.member_count_for_org",
        _count,
    )

    await assert_batch_member_capacity(db, org, members, "en")


@pytest.mark.asyncio
async def test_assert_batch_member_capacity_rejects_at_effective_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = as_organization(type("Org", (), {"id": 1, "school_tier": SCHOOL_TIER_LITE, "extra_member_seats": 10})())
    members = [SchoolMemberInput(phone="13812345678", email=None, name="New", role="teacher")]
    db = AsyncMock()

    async def _count(_db, _org_id):
        return 60

    monkeypatch.setattr(
        "services.auth.school_user_create.member_count_for_org",
        _count,
    )

    with pytest.raises(HTTPException) as exc:
        await assert_batch_member_capacity(db, org, members, "en")
    assert exc.value.status_code == 403
