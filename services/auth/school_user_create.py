"""Create org-scoped school members from the school dashboard."""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from email_validator import EmailNotValidError
from email_validator import validate_email as ev_validate
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages
from services.auth.phone_uniqueness import any_user_id_with_email, any_user_id_with_phone
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
    """SchoolMemberInput helper."""

    phone: str | None
    email: str | None
    name: str
    role: str

    @property
    def contact_key(self) -> str:
        """Contact key."""
        return self.phone or self.email or ""


@dataclass(frozen=True)
class SchoolMemberBatchFailure:
    """SchoolMemberBatchFailure helper."""

    index: int
    phone: str | None
    email: str | None
    name: str
    detail: str


def normalize_school_member_phone(phone: str) -> str:
    """Normalize school member phone."""
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
    """Validate school member phone."""
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


def try_normalize_school_member_email(email: str) -> str | None:
    """Try normalize school member email."""
    value = str(email or "").strip()
    if not value:
        return None
    try:
        return ev_validate(value, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def validate_school_member_email(email: str, lang: Language) -> str:
    """Validate school member email."""
    normalized = try_normalize_school_member_email(email)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("email_invalid_format", lang=lang),
        )
    return normalized


def validate_school_member_name(name: str, lang: Language) -> str:
    """Validate school member name."""
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
    """Validate school member role."""
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


def _batch_failure_from_item(
    index: int,
    item: dict[str, Any],
    name: str,
    detail: str,
) -> SchoolMemberBatchFailure:
    """Batch failure from item."""
    raw_phone = item.get("phone")
    raw_email = item.get("email")
    phone = str(raw_phone).strip() if raw_phone is not None and str(raw_phone).strip() else None
    email = str(raw_email).strip() if raw_email is not None and str(raw_email).strip() else None
    return SchoolMemberBatchFailure(
        index=index,
        phone=phone,
        email=email,
        name=name,
        detail=detail,
    )


def try_parse_school_member_item(
    item: dict[str, Any],
    lang: Language,
    *,
    actor_role: str | None = None,
) -> tuple[SchoolMemberInput | None, SchoolMemberBatchFailure | None]:
    """Try parse school member item."""
    name_raw = str(item.get("name", "") or "").strip()
    raw_phone = item.get("phone")
    raw_email = item.get("email")
    has_phone = raw_phone is not None and str(raw_phone).strip()
    has_email = raw_email is not None and str(raw_email).strip()

    if has_phone and has_email:
        display_name = name_raw or str(raw_phone)
        return None, _batch_failure_from_item(
            0,
            item,
            display_name,
            Messages.error("school_user_batch_both_contact", lang, display_name),
        )

    if not has_phone and not has_email:
        display_name = name_raw or Messages.error("school_user_batch_unknown_member", lang)
        return None, _batch_failure_from_item(
            0,
            item,
            display_name,
            Messages.error("school_user_batch_missing_contact", lang, display_name),
        )

    try:
        name = validate_school_member_name(name_raw, lang)
    except HTTPException:
        display_name = name_raw or str(raw_phone or raw_email or "")
        return None, _batch_failure_from_item(
            0,
            item,
            display_name,
            Messages.error("school_user_batch_invalid_name_for_name", lang, display_name),
        )

    phone: str | None = None
    email: str | None = None
    if has_phone:
        normalized_phone = normalize_school_member_phone(str(raw_phone))
        if len(normalized_phone) != 11 or not normalized_phone.isdigit() or not normalized_phone.startswith("1"):
            return None, _batch_failure_from_item(
                0,
                item,
                name,
                Messages.error("school_user_batch_invalid_phone_for_name", lang, name),
            )
        phone = normalized_phone
    else:
        normalized_email = try_normalize_school_member_email(str(raw_email))
        if not normalized_email:
            return None, _batch_failure_from_item(
                0,
                item,
                name,
                Messages.error("school_user_batch_invalid_email_for_name", lang, name),
            )
        email = normalized_email

    try:
        role = validate_school_member_role(item.get("role"), lang, actor_role=actor_role)
    except HTTPException as exc:
        return None, _batch_failure_from_item(0, item, name, str(exc.detail))

    return SchoolMemberInput(phone=phone, email=email, name=name, role=role), None


def parse_school_member_input(
    raw: dict[str, Any],
    lang: Language,
    *,
    actor_role: str | None = None,
) -> SchoolMemberInput:
    """Parse school member input."""
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang=lang),
        )
    member, failure = try_parse_school_member_item(raw, lang, actor_role=actor_role)
    if failure is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=failure.detail,
        )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang=lang),
        )
    return member


def parse_school_member_batch(
    raw_members: object,
    lang: Language,
    *,
    actor_role: str | None = None,
) -> tuple[list[SchoolMemberInput], list[SchoolMemberBatchFailure]]:
    """Parse school member batch."""
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
    failed: list[SchoolMemberBatchFailure] = []
    seen_contacts: set[str] = set()
    for index, item in enumerate(raw_members):
        if not isinstance(item, dict):
            failed.append(
                SchoolMemberBatchFailure(
                    index=index + 1,
                    phone=None,
                    email=None,
                    name="",
                    detail=Messages.error("school_user_batch_invalid_row", lang, index + 1),
                )
            )
            continue

        member, failure = try_parse_school_member_item(item, lang, actor_role=actor_role)
        if failure is not None:
            failed.append(
                SchoolMemberBatchFailure(
                    index=index + 1,
                    phone=failure.phone,
                    email=failure.email,
                    name=failure.name,
                    detail=failure.detail,
                )
            )
            continue
        if member is None or not member.contact_key:
            failed.append(
                SchoolMemberBatchFailure(
                    index=index + 1,
                    phone=None,
                    email=None,
                    name=str(item.get("name", "") or ""),
                    detail=Messages.error("school_user_batch_invalid_row", lang, index + 1),
                )
            )
            continue
        if member.contact_key in seen_contacts:
            continue
        seen_contacts.add(member.contact_key)
        parsed.append(member)

    if not parsed and not failed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_user_batch_empty", lang=lang),
        )
    return parsed, failed


async def assert_batch_member_capacity(
    db: AsyncSession,
    org: Organization,
    members: list[SchoolMemberInput],
    lang: Language,
) -> None:
    """Assert batch member capacity."""
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
    """Create school member user."""
    if member.phone and await any_user_id_with_phone(member.phone) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("phone_already_registered_other", lang, member.phone),
        )
    if member.email and await any_user_id_with_email(member.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("email_already_registered_other", lang, member.email),
        )

    if member.role == ROLE_SCHOOL_ADMIN:
        await assert_organization_has_manager_capacity(db, org, lang)
    await assert_organization_has_member_capacity(db, org, lang)

    placeholder_password = hash_password(secrets.token_urlsafe(32))
    new_user = User(
        phone=member.phone,
        email=member.email,
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
) -> tuple[list[User], list[SchoolMemberBatchFailure], int]:
    """Create school member batch."""
    phones = [member.phone for member in members if member.phone]
    emails = [member.email for member in members if member.email]
    contact_filters = []
    if phones:
        contact_filters.append(User.phone.in_(phones))
    if emails:
        contact_filters.append(User.email.in_(emails))

    existing_phones: set[str] = set()
    existing_emails: set[str] = set()
    if contact_filters:
        existing_rows = (await db.execute(select(User.phone, User.email).where(or_(*contact_filters)))).all()
        for phone, email in existing_rows:
            if phone:
                existing_phones.add(str(phone))
            if email:
                existing_emails.add(str(email))

    skipped_count = 0
    pending: list[SchoolMemberInput] = []
    for member in members:
        if member.phone and member.phone in existing_phones:
            skipped_count += 1
            continue
        if member.email and member.email in existing_emails:
            skipped_count += 1
            continue
        pending.append(member)

    await assert_batch_member_capacity(db, org, pending, lang)

    created: list[User] = []
    failed: list[SchoolMemberBatchFailure] = []
    placeholder_password = hash_password(secrets.token_urlsafe(32))

    for member in pending:
        new_user = User(
            phone=member.phone,
            email=member.email,
            password_hash=placeholder_password,
            name=member.name,
            organization_id=org.id,
            created_at=datetime.now(UTC),
            role=member.role,
            login_password_set=False,
        )
        db.add(new_user)
        created.append(new_user)
        if member.phone:
            existing_phones.add(member.phone)
        if member.email:
            existing_emails.add(member.email)

    if created:
        await db.flush()
    return created, failed, skipped_count


def batch_result_payload(
    created: list[User],
    failed: list[SchoolMemberBatchFailure],
    lang: Language,
    *,
    skipped_count: int = 0,
) -> dict[str, Any]:
    """Batch result payload."""
    created_count = len(created)
    failed_count = len(failed)
    if failed_count == 0 and created_count == 0 and skipped_count > 0:
        message = Messages.success("school_user_batch_all_skipped", lang, skipped_count)
    elif failed_count == 0:
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
        "skipped_count": skipped_count,
        "created": [
            {
                "id": user.id,
                "phone": user.phone,
                "email": user.email,
                "name": user.name,
                "role": normalize_role(getattr(user, "role", ROLE_TEACHER)),
            }
            for user in created
        ],
        "failed": [
            {
                "index": item.index,
                "phone": item.phone,
                "email": item.email,
                "name": item.name,
                "detail": item.detail,
            }
            for item in failed
        ],
    }
