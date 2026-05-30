"""Unit tests for school dashboard member creation helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.auth.school_user_create import (
    MAX_BATCH_MEMBERS,
    normalize_school_member_phone,
    parse_school_member_batch,
    parse_school_member_input,
    validate_school_member_phone,
)
from utils.auth.role_constants import ROLE_SCHOOL_ADMIN, ROLE_SUPERADMIN


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


def test_parse_school_member_input_normalizes_fields() -> None:
    member = parse_school_member_input(
        {"phone": "13812345678", "name": "  Zhang San  ", "role": "teacher"},
        "en",
    )
    assert member.phone == "13812345678"
    assert member.name == "Zhang San"
    assert member.role == "teacher"


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


def test_parse_school_member_batch_deduplicates_phones() -> None:
    members = parse_school_member_batch(
        [
            {"phone": "13812345678", "name": "A"},
            {"phone": "13812345678", "name": "B"},
            {"phone": "13812345679", "name": "C"},
        ],
        "en",
    )
    assert len(members) == 2
    assert members[0].phone == "13812345678"
    assert members[1].phone == "13812345679"


def test_parse_school_member_batch_rejects_too_many_rows() -> None:
    payload = [
        {"phone": f"138{index:08d}", "name": f"User{index}"}
        for index in range(MAX_BATCH_MEMBERS + 1)
    ]
    with pytest.raises(HTTPException) as exc:
        parse_school_member_batch(payload, "en")
    assert exc.value.status_code == 400
