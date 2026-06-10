"""Create org-scoped school members from the school dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
import secrets
import unicodedata
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages
from services.auth.phone_uniqueness import any_user_id_with_phone
from utils.auth import hash_password
from utils.auth.role_constants import ROLE_SCHOOL_ADMIN, ROLE_SUPERADMIN, ROLE_TEACHER, normalize_role
from utils.auth.school_tier import (
    assert_organization_has_manager_capacity,
    assert_organization_has_member_capacity,
    is_unlimited_member_limit,
    manager_count_for_org,
    manager_limit_for_org,
    member_count_for_org,
    member_limit_for_org,
)

ALLOWED_SCHOOL_MEMBER_ROLES = frozenset({ROLE_TEACHER, ROLE_SCHOOL_ADMIN})
MAX_BATCH_MEMBERS = 200
MAX_MEMBER_NAME_LENGTH = 200


@dataclass(frozen=True)
class SchoolMemberInput:
    phone: str
    name: str
    role: str


@dataclass(frozen=True)
class SchoolMemberBatchFailure:
    index: int
    phone: str
    name: str
    detail: str


def normalize_school_member_phone(phone: str) -> str:
    normalized_cell = unicodedata.normalize("NFKC", str(phone or "").strip())
    trimmed = normalized_cell.strip()
    if re.fullmatch(r"[\d.]+[eE][+\-]?\d+", trimmed):
        numeric = float(trimmed)
        if 1_000_000_000 <= numeric < 100_000_000_000:
            return str(round(numeric))
    if re.fullmatch(r"\d+\.0+", trimmed):
        return trimmed.split(".", maxsplit=1)[0]
    digits = re.sub(r"\D", "", trimmed)
    if len(digits) == 13 and digits.startswith("86"):
        return digits[2:]
    return digits


def validate_school_member_phone(phone: str, lang: Language) -> str:
    normalized = normalize_school_member_phone(phone)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("phone_cannot_be_empty", lang=lang),
        )
    if len(normalized) != 11 or not normalized.isdigit() or not normalized.startswith("1"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("phone_format_invalid", lang=lang),
        )
    return normalized


def validate_school_member_name(name: str, lang: Language) -> str:
    normalized = str(name or "").strip()
    if not normalized or len(normalized) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("name_too_short", lang=lang),
        )
    if any(char.isdigit() for char in normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("name_cannot_contain_numbers", lang=lang),
        )
    if len(normalized) > MAX_MEMBER_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("name_too_long", MAX_MEMBER_NAME_LENGTH, lang=lang),
        )
    return normalized


def validate_school_member_role(
    raw_role: object | None,
    lang: Language,
    *,
    actor_role: str | None = None,
) -> str:
    role = normalize_role(str(raw_role or ROLE_TEACHER))
    if role not in ALLOWED_SCHOOL_MEMBER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_create_invalid_role", lang=lang),
        )
    actor = normalize_role(str(actor_role or ""))
    if role == ROLE_SCHOOL_ADMIN and actor != ROLE_SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("school_user_create_manager_role_denied", lang=lang),
        )
    return role


def parse_school_member_input(
    raw: dict[str, Any],
    lang: Language,
    *,
    actor_role: str | None = None,
) -> SchoolMemberInput:
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang=lang),
        )
    phone = validate_school_member_phone(str(raw.get("phone", "")), lang)
    name = validate_school_member_name(str(raw.get("name", "")), lang)
    role = validate_school_member_role(raw.get("role"), lang, actor_role=actor_role)
    return SchoolMemberInput(phone=phone, name=name, role=role)


def parse_school_member_batch(
    raw_members: object,
    lang: Language,
    *,
    actor_role: str | None = None,
) -> list[SchoolMemberInput]:
    if not isinstance(raw_members, list) or not raw_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_batch_empty", lang=lang),
        )
    if len(raw_members) > MAX_BATCH_MEMBERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_batch_too_large", lang, MAX_BATCH_MEMBERS),
        )

    parsed: list[SchoolMemberInput] = []
    seen_phones: set[str] = set()
    for index, item in enumerate(raw_members):
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("school_user_batch_invalid_row", lang, index + 1),
            )
        member = parse_school_member_input(item, lang, actor_role=actor_role)
        if member.phone in seen_phones:
            continue
        seen_phones.add(member.phone)
        parsed.append(member)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_batch_empty", lang=lang),
        )
    return parsed


async def assert_batch_member_capacity(
    db: AsyncSession,
    org: Organization,
    members: list[SchoolMemberInput],
    lang: Language,
) -> None:
    current_members = await member_count_for_org(db, int(org.id))
    max_members = member_limit_for_org(org)
    if not is_unlimited_member_limit(max_members) and current_members + len(members) > max_members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("organization_member_limit_reached", lang, max_members),
        )

    new_manager_count = sum(1 for member in members if member.role == ROLE_SCHOOL_ADMIN)
    if new_manager_count <= 0:
        return

    current_managers = await manager_count_for_org(db, int(org.id))
    max_managers = manager_limit_for_org(org)
    if current_managers + new_manager_count > max_managers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("organization_manager_limit_reached", lang, max_managers),
        )


async def create_school_member_user(
    db: AsyncSession,
    org: Organization,
    member: SchoolMemberInput,
    lang: Language,
) -> User:
    if await any_user_id_with_phone(member.phone) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("phone_already_registered_other", lang, member.phone),
        )

    if member.role == ROLE_SCHOOL_ADMIN:
        await assert_organization_has_manager_capacity(db, org, lang)
    await assert_organization_has_member_capacity(db, org, lang)

    placeholder_password = hash_password(secrets.token_urlsafe(32))
    new_user = User(
        phone=member.phone,
        password_hash=placeholder_password,
        name=member.name,
        organization_id=org.id,
        created_at=datetime.now(UTC),
        role=member.role,
        login_password_set=False,
    )
    db.add(new_user)
    await db.flush()
    return new_user


async def create_school_member_batch(
    db: AsyncSession,
    org: Organization,
    members: list[SchoolMemberInput],
    lang: Language,
) -> tuple[list[User], list[SchoolMemberBatchFailure]]:
    await assert_batch_member_capacity(db, org, members, lang)

    phones = [member.phone for member in members]
    existing_rows = (await db.execute(select(User.phone).where(User.phone.in_(phones)))).scalars().all()
    existing_phones = {str(phone) for phone in existing_rows if phone}

    created: list[User] = []
    failed: list[SchoolMemberBatchFailure] = []
    placeholder_password = hash_password(secrets.token_urlsafe(32))

    for index, member in enumerate(members):
        if member.phone in existing_phones:
            failed.append(
                SchoolMemberBatchFailure(
                    index=index + 1,
                    phone=member.phone,
                    name=member.name,
                    detail=Messages.error("phone_already_registered_other", lang, member.phone),
                )
            )
            continue

        new_user = User(
            phone=member.phone,
            password_hash=placeholder_password,
            name=member.name,
            organization_id=org.id,
            created_at=datetime.now(UTC),
            role=member.role,
            login_password_set=False,
        )
        db.add(new_user)
        created.append(new_user)
        existing_phones.add(member.phone)

    if created:
        await db.flush()
    return created, failed


def batch_result_payload(
    created: list[User],
    failed: list[SchoolMemberBatchFailure],
    lang: Language,
) -> dict[str, Any]:
    created_count = len(created)
    failed_count = len(failed)
    if failed_count == 0:
        message = Messages.success("school_user_batch_created", lang, created_count)
    elif created_count == 0:
        message = Messages.error("school_user_batch_all_failed", lang)
    else:
        message = Messages.success(
            "school_user_batch_partial",
            lang,
            created_count,
            failed_count,
        )

    return {
        "message": message,
        "created_count": created_count,
        "failed_count": failed_count,
        "created": [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name,
                "role": normalize_role(getattr(user, "role", ROLE_TEACHER)),
            }
            for user in created
        ],
        "failed": [
            {
                "index": item.index,
                "phone": item.phone,
                "name": item.name,
                "detail": item.detail,
            }
            for item in failed
        ],
    }
