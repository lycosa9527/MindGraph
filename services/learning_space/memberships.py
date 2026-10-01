"""Class memberships: enrolled learners and review-only assistants.

Classroom students stay on ``users.learning_class_id`` + ``role=student``.
Existing accounts join a class via this table without changing ``users.role``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import String, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_DRAFT,
    CLASS_STATUS_ACTIVE,
    MEMBERSHIP_ROLE_ASSISTANT,
    MEMBERSHIP_ROLE_LEARNER,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningClass,
    LearningClassMembership,
    LearningSubmission,
)
from services.learning_space.admin_teachers import organization_display_map, user_display_map
from services.learning_space.passwords import staff_visible_learning_space_password
from utils.auth.role_constants import ROLE_STUDENT
from utils.auth.roles import is_student
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def normalize_account_phone(raw: str) -> str:
    """Keep digits only for phone lookup."""
    return "".join(ch for ch in (raw or "").strip() if ch.isdigit())


def parse_account_phones(text: str) -> list[str]:
    """Split pasted phones (one per line or comma-separated), preserving order."""
    seen: set[str] = set()
    phones: list[str] = []
    for chunk in (text or "").replace("，", ",").replace("；", ";").replace("\n", ",").split(","):
        phone = chunk.strip()
        if not phone:
            continue
        key = normalize_account_phone(phone) or phone
        if key in seen:
            continue
        seen.add(key)
        phones.append(phone.strip())
    return phones


@dataclass
class AccountImportPreviewRow:
    """One existing-account import preview line."""

    phone: str
    ok: bool
    error: str | None = None
    user_id: int | None = None
    name: str | None = None
    organization_name: str | None = None
    role: str | None = None


async def count_classroom_students(db: AsyncSession, class_id: int) -> int:
    """Count dedicated Learning Space student accounts in a class."""
    result = await db.execute(
        select(func.count()).select_from(User).where(User.learning_class_id == class_id, User.role == ROLE_STUDENT)
    )
    return int(result.scalar_one() or 0)


async def count_class_learners(db: AsyncSession, class_id: int) -> int:
    """Count enrolled learner memberships (not assistants)."""
    result = await db.execute(
        select(func.count())
        .select_from(LearningClassMembership)
        .where(
            LearningClassMembership.class_id == class_id,
            LearningClassMembership.role == MEMBERSHIP_ROLE_LEARNER,
        )
    )
    return int(result.scalar_one() or 0)


async def membership_role_for_user(db: AsyncSession, user_id: int, class_id: int) -> str | None:
    """Return learner/assistant for this class, if enrolled."""
    result = await db.execute(
        select(LearningClassMembership.role).where(
            LearningClassMembership.user_id == user_id,
            LearningClassMembership.class_id == class_id,
        )
    )
    role = result.scalar_one_or_none()
    return str(role) if role else None


async def is_class_learner(db: AsyncSession, user_id: int, class_id: int) -> bool:
    """True when the user is an enrolled learner in the class."""
    return await membership_role_for_user(db, user_id, class_id) == MEMBERSHIP_ROLE_LEARNER


async def is_class_assistant(db: AsyncSession, user_id: int, class_id: int) -> bool:
    """True when the user is a review-only assistant in the class."""
    return await membership_role_for_user(db, user_id, class_id) == MEMBERSHIP_ROLE_ASSISTANT


async def class_ids_for_membership_role(db: AsyncSession, user_id: int, role: str) -> list[int]:
    """Class ids where the user holds the given membership role."""
    result = await db.execute(
        select(LearningClassMembership.class_id).where(
            LearningClassMembership.user_id == user_id,
            LearningClassMembership.role == role,
        )
    )
    return [int(cid) for (cid,) in result.all()]


async def learner_class_ids(db: AsyncSession, user: User) -> list[int]:
    """Active classes the user may complete homework in (classroom + enrolled)."""
    ids: list[int] = []
    if is_student(user) and user.learning_class_id:
        ids.append(int(user.learning_class_id))
    ids.extend(await class_ids_for_membership_role(db, int(user.id), MEMBERSHIP_ROLE_LEARNER))
    unique = list(dict.fromkeys(ids))
    if not unique:
        return []
    result = await db.execute(
        select(LearningClass.id).where(
            LearningClass.id.in_(tuple(unique)),
            LearningClass.status == CLASS_STATUS_ACTIVE,
        )
    )
    active = {int(cid) for (cid,) in result.all()}
    return [cid for cid in unique if cid in active]


async def class_activity_stats(db: AsyncSession, class_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per-class assignment count (non-draft) and submitted-work count."""
    empty = {cid: {"assignment_count": 0, "submission_count": 0} for cid in class_ids}
    if not class_ids:
        return empty
    asg = await db.execute(
        select(LearningAssignment.class_id, func.count())
        .where(
            LearningAssignment.class_id.in_(tuple(class_ids)),
            LearningAssignment.status != ASSIGNMENT_STATUS_DRAFT,
        )
        .group_by(LearningAssignment.class_id)
    )
    for class_id, count in asg.all():
        empty[int(class_id)]["assignment_count"] = int(count or 0)
    sub = await db.execute(
        select(LearningAssignment.class_id, func.count())
        .select_from(LearningSubmission)
        .join(LearningAssignment, LearningAssignment.id == LearningSubmission.assignment_id)
        .where(
            LearningAssignment.class_id.in_(tuple(class_ids)),
            LearningSubmission.status == SUBMISSION_STATUS_SUBMITTED,
        )
        .group_by(LearningAssignment.class_id)
    )
    for class_id, count in sub.all():
        empty[int(class_id)]["submission_count"] = int(count or 0)
    return empty


async def assistants_by_class(db: AsyncSession, class_ids: list[int]) -> dict[int, list[dict]]:
    """Map class id → assistant user summaries."""
    if not class_ids:
        return {}
    result = await db.execute(
        select(LearningClassMembership, User)
        .join(User, User.id == LearningClassMembership.user_id)
        .where(
            LearningClassMembership.class_id.in_(tuple(class_ids)),
            LearningClassMembership.role == MEMBERSHIP_ROLE_ASSISTANT,
        )
        .order_by(LearningClassMembership.id)
    )
    rows = list(result.all())
    org_ids = {int(user.organization_id) for _, user in rows if user.organization_id is not None}
    org_names = await organization_display_map(org_ids)
    grouped: dict[int, list[dict]] = {cid: [] for cid in class_ids}
    for membership, user in rows:
        org_id = int(user.organization_id) if user.organization_id is not None else None
        grouped.setdefault(int(membership.class_id), []).append(
            {
                "id": int(user.id),
                "name": (user.name or "").strip() or (user.phone or ""),
                "phone": user.phone,
                "organization_name": org_names.get(org_id, "") if org_id is not None else "",
            }
        )
    return grouped


async def find_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """Match a registered user by stored phone (exact, digits, or last 11)."""
    raw = (phone or "").strip()
    digits = normalize_account_phone(raw)
    if raw:
        result = await db.execute(select(User).where(User.phone == raw))
        user = result.scalar_one_or_none()
        if user is not None:
            return user
    if digits and digits != raw:
        result = await db.execute(select(User).where(User.phone == digits))
        user = result.scalar_one_or_none()
        if user is not None:
            return user
    if len(digits) >= 11:
        suffix = digits[-11:]
        result = await db.execute(select(User).where(User.phone.like(f"%{suffix}")))
        matches = list(result.scalars().all())
        if len(matches) == 1:
            return matches[0]
    return None


async def _org_name_for_user(user: User) -> str:
    if user.organization_id is None:
        return ""
    names = await organization_display_map({int(user.organization_id)})
    return names.get(int(user.organization_id), "")


async def preview_existing_accounts(
    db: AsyncSession, learning_class: LearningClass, phones: list[str]
) -> list[AccountImportPreviewRow]:
    """Validate phones for learner import (no writes)."""
    rows: list[AccountImportPreviewRow] = []
    current_count = await _roster_headcount(db, learning_class.id)
    ok_count = 0
    seen_users: set[int] = set()
    for phone in phones:
        user = await find_user_by_phone(db, phone)
        if user is None:
            rows.append(AccountImportPreviewRow(phone=phone, ok=False, error="not_found"))
            continue
        if int(user.id) in seen_users:
            rows.append(
                AccountImportPreviewRow(
                    phone=phone,
                    ok=False,
                    error="already_member",
                    user_id=int(user.id),
                    name=user.name,
                    organization_name=await _org_name_for_user(user),
                    role=user.role,
                )
            )
            continue
        error = await _import_block_reason(db, learning_class, user)
        if error:
            rows.append(
                AccountImportPreviewRow(
                    phone=phone,
                    ok=False,
                    error=error,
                    user_id=int(user.id),
                    name=user.name,
                    organization_name=await _org_name_for_user(user),
                    role=user.role,
                )
            )
            continue
        if current_count + ok_count >= int(learning_class.max_students):
            rows.append(
                AccountImportPreviewRow(
                    phone=phone,
                    ok=False,
                    error="class_full",
                    user_id=int(user.id),
                    name=user.name,
                    organization_name=await _org_name_for_user(user),
                    role=user.role,
                )
            )
            continue
        ok_count += 1
        seen_users.add(int(user.id))
        rows.append(
            AccountImportPreviewRow(
                phone=phone,
                ok=True,
                user_id=int(user.id),
                name=user.name,
                organization_name=await _org_name_for_user(user),
                role=user.role,
            )
        )
    return rows


async def _roster_headcount(db: AsyncSession, class_id: int) -> int:
    classroom = await count_classroom_students(db, class_id)
    learners = await count_class_learners(db, class_id)
    return classroom + learners


async def _import_block_reason(db: AsyncSession, learning_class: LearningClass, user: User) -> str | None:
    if is_student(user):
        return "classroom_student"
    if int(user.id) == int(learning_class.teacher_user_id):
        return "is_class_teacher"
    existing = await membership_role_for_user(db, int(user.id), int(learning_class.id))
    if existing == MEMBERSHIP_ROLE_LEARNER:
        return "already_member"
    if existing == MEMBERSHIP_ROLE_ASSISTANT:
        return "already_assistant"
    return None


async def import_existing_accounts(db: AsyncSession, learning_class: LearningClass, phones: list[str]) -> dict:
    """Enroll existing accounts as learners; never changes ``users.role``."""
    preview = await preview_existing_accounts(db, learning_class, phones)
    created: list[dict] = []
    failed: list[dict] = []
    for row in preview:
        if not row.ok or row.user_id is None:
            failed.append({"phone": row.phone, "error": row.error or "invalid"})
            continue
        membership = LearningClassMembership(
            class_id=int(learning_class.id),
            user_id=int(row.user_id),
            organization_id=int(learning_class.organization_id),
            role=MEMBERSHIP_ROLE_LEARNER,
        )
        db.add(membership)
        created.append(
            {
                "user_id": row.user_id,
                "phone": row.phone,
                "name": row.name,
                "organization_name": row.organization_name,
            }
        )
    await db.commit()
    logger.info(
        "[LearningSpace] Enrolled accounts class=%s created=%s failed=%s",
        learning_class.id,
        len(created),
        len(failed),
    )
    return {"created": created, "failed": failed}


async def replace_class_assistants(db: AsyncSession, learning_class: LearningClass, user_ids: list[int]) -> list[dict]:
    """Replace assistant list. Learners in the payload are promoted; others enrolled as assistants."""
    unique_ids = list(dict.fromkeys(int(uid) for uid in user_ids if uid > 0))
    existing = await db.execute(
        select(LearningClassMembership).where(
            LearningClassMembership.class_id == learning_class.id,
            LearningClassMembership.role == MEMBERSHIP_ROLE_ASSISTANT,
        )
    )
    for row in existing.scalars().all():
        if int(row.user_id) not in unique_ids:
            await db.delete(row)

    kept: list[dict] = []
    for user_id in unique_ids:
        if user_id == int(learning_class.teacher_user_id):
            continue
        user = await db.get(User, user_id)
        if user is None or is_student(user):
            continue
        current = await db.execute(
            select(LearningClassMembership).where(
                LearningClassMembership.class_id == learning_class.id,
                LearningClassMembership.user_id == user_id,
            )
        )
        membership = current.scalar_one_or_none()
        if membership is None:
            membership = LearningClassMembership(
                class_id=int(learning_class.id),
                user_id=user_id,
                organization_id=int(learning_class.organization_id),
                role=MEMBERSHIP_ROLE_ASSISTANT,
            )
            db.add(membership)
        else:
            membership.role = MEMBERSHIP_ROLE_ASSISTANT
        kept.append({"id": user_id, "name": (user.name or "").strip() or (user.phone or "")})
    await db.flush()
    logger.info(
        "[LearningSpace] Assistants replaced class=%s count=%s",
        learning_class.id,
        len(kept),
    )
    return kept


async def organization_info_map(org_ids: set[int]) -> dict[int, dict[str, str]]:
    """Map organization id → name + school_tier."""
    if not org_ids:
        return {}
    async with system_rls_session() as db:
        result = await db.execute(
            select(
                Organization.id,
                Organization.name,
                Organization.display_name,
                Organization.school_tier,
            ).where(Organization.id.in_(tuple(org_ids)))
        )
        info: dict[int, dict[str, str]] = {}
        for oid, name, display_name, school_tier in result.all():
            label = (display_name or "").strip() or (name or "").strip()
            info[int(oid)] = {
                "organization_name": label,
                "school_tier": str(school_tier or ""),
            }
        return info


def _admin_student_list_selects():
    """Shared columns for classroom students and enrolled learners."""
    classroom = (
        select(
            User.id.label("user_id"),
            User.name.label("name"),
            User.phone.label("phone"),
            User.role.label("role"),
            User.must_change_password.label("must_change_password"),
            User.last_login.label("last_login"),
            User.learning_space_login_password.label("learning_space_login_password"),
            literal("classroom").label("member_kind"),
            literal(None, type_=String).label("membership_role"),
            LearningClass.id.label("class_id"),
            LearningClass.name.label("class_name"),
            LearningClass.class_code.label("class_code"),
            LearningClass.status.label("class_status"),
            LearningClass.teacher_user_id.label("teacher_user_id"),
            LearningClass.organization_id.label("organization_id"),
        )
        .join(LearningClass, User.learning_class_id == LearningClass.id)
        .where(User.role == ROLE_STUDENT, User.learning_class_id.isnot(None))
    )
    enrolled = (
        select(
            User.id.label("user_id"),
            User.name.label("name"),
            User.phone.label("phone"),
            User.role.label("role"),
            User.must_change_password.label("must_change_password"),
            User.last_login.label("last_login"),
            literal(None, type_=String).label("learning_space_login_password"),
            literal("enrolled").label("member_kind"),
            LearningClassMembership.role.label("membership_role"),
            LearningClass.id.label("class_id"),
            LearningClass.name.label("class_name"),
            LearningClass.class_code.label("class_code"),
            LearningClass.status.label("class_status"),
            LearningClass.teacher_user_id.label("teacher_user_id"),
            LearningClass.organization_id.label("organization_id"),
        )
        .select_from(LearningClassMembership)
        .join(User, User.id == LearningClassMembership.user_id)
        .join(LearningClass, LearningClass.id == LearningClassMembership.class_id)
        .where(LearningClassMembership.role == MEMBERSHIP_ROLE_LEARNER)
    )
    return classroom, enrolled


async def list_admin_students_global(
    _db: AsyncSession,
    *,
    class_id: int | None = None,
    member_kind: str | None = None,
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Paginated cross-class student roster for admin panel."""
    del _db  # Admin roster spans users + memberships; use system RLS like org lookups.
    async with system_rls_session() as admin_db:
        return await _list_admin_students_global_body(
            admin_db,
            class_id=class_id,
            member_kind=member_kind,
            search=search,
            page=page,
            page_size=page_size,
        )


async def _list_admin_students_global_body(
    db: AsyncSession,
    *,
    class_id: int | None = None,
    member_kind: str | None = None,
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Implementation for ``list_admin_students_global`` (system RLS session)."""
    classroom, enrolled = _admin_student_list_selects()
    if class_id is not None:
        classroom = classroom.where(LearningClass.id == class_id)
        enrolled = enrolled.where(LearningClass.id == class_id)
    if member_kind == "classroom":
        combined = classroom.subquery()
    elif member_kind == "enrolled":
        combined = enrolled.subquery()
    else:
        combined = union_all(classroom, enrolled).subquery()

    filters = []
    if search.strip():
        term = f"%{search.strip()}%"
        filters.append((combined.c.name.like(term)) | (combined.c.phone.like(term)))

    count_stmt = select(func.count()).select_from(combined)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)

    classroom_count_stmt = select(func.count()).select_from(classroom.subquery())
    enrolled_count_stmt = select(func.count()).select_from(enrolled.subquery())
    classroom_total = int((await db.execute(classroom_count_stmt)).scalar_one() or 0)
    enrolled_total = int((await db.execute(enrolled_count_stmt)).scalar_one() or 0)

    list_stmt = select(combined)
    if filters:
        list_stmt = list_stmt.where(*filters)
    skip = max(page - 1, 0) * page_size
    list_stmt = list_stmt.order_by(combined.c.user_id.desc()).offset(skip).limit(page_size)
    rows = list((await db.execute(list_stmt)).all())

    org_ids = {int(row.organization_id) for row in rows if row.organization_id is not None}
    teacher_ids = {int(row.teacher_user_id) for row in rows if row.teacher_user_id is not None}
    org_names = await organization_display_map(org_ids)
    teacher_names = await user_display_map(teacher_ids)

    items: list[dict] = []
    for row in rows:
        org_id = int(row.organization_id) if row.organization_id is not None else None
        teacher_id = int(row.teacher_user_id) if row.teacher_user_id is not None else None
        items.append(
            {
                "id": int(row.user_id),
                "name": (row.name or "").strip() or (row.phone or ""),
                "phone": row.phone,
                "role": row.role,
                "member_kind": row.member_kind,
                "membership_role": row.membership_role,
                "must_change_password": bool(row.must_change_password),
                "last_login": row.last_login.isoformat() if row.last_login else None,
                "class_id": int(row.class_id),
                "class_name": row.class_name or "",
                "class_code": row.class_code or "",
                "class_status": row.class_status or "",
                "teacher_user_id": teacher_id,
                "teacher_name": teacher_names.get(teacher_id, "") if teacher_id is not None else "",
                "organization_id": org_id,
                "organization_name": org_names.get(org_id, "") if org_id is not None else "",
                "initial_password": staff_visible_learning_space_password(
                    name=(row.name or "").strip() or (row.phone or ""),
                    role=str(row.role or ""),
                    learning_class_id=int(row.class_id) if row.member_kind == "classroom" else None,
                    must_change_password=bool(row.must_change_password),
                    stored_password=getattr(row, "learning_space_login_password", None),
                    include=row.member_kind == "classroom",
                ),
            }
        )

    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
        "summary": {
            "classroom_count": classroom_total,
            "enrolled_count": enrolled_total,
            "total": classroom_total + enrolled_total,
        },
    }


async def class_roster_items(
    db: AsyncSession,
    class_id: int,
    *,
    include_initial_password: bool = True,
    admin_bypass_rls: bool = False,
) -> list[dict]:
    """Classroom students plus enrolled members (learners and assistants)."""
    if admin_bypass_rls:
        async with system_rls_session() as admin_db:
            return await class_roster_items(
                admin_db,
                class_id,
                include_initial_password=include_initial_password,
                admin_bypass_rls=False,
            )
    classroom = await db.execute(
        select(User).where(User.learning_class_id == class_id, User.role == ROLE_STUDENT).order_by(User.id)
    )
    members = await db.execute(
        select(LearningClassMembership, User)
        .join(User, User.id == LearningClassMembership.user_id)
        .where(LearningClassMembership.class_id == class_id)
        .order_by(LearningClassMembership.id)
    )
    member_rows = list(members.all())
    org_ids = {int(user.organization_id) for _, user in member_rows if user.organization_id is not None}
    org_info = await organization_info_map(org_ids)
    items: list[dict] = []
    for student in classroom.scalars().all():
        items.append(
            {
                "id": int(student.id),
                "name": student.name or "",
                "phone": student.phone,
                "role": student.role,
                "school_tier": None,
                "organization_name": "",
                "member_kind": "classroom",
                "membership_role": None,
                "initial_password": staff_visible_learning_space_password(
                    name=student.name or "",
                    role=student.role,
                    learning_class_id=int(student.learning_class_id) if student.learning_class_id else None,
                    must_change_password=bool(student.must_change_password),
                    stored_password=getattr(student, "learning_space_login_password", None),
                    include=include_initial_password,
                ),
                "must_change_password": bool(student.must_change_password),
                "last_login": student.last_login.isoformat() if student.last_login else None,
            }
        )
    for membership, user in member_rows:
        org_id = int(user.organization_id) if user.organization_id is not None else None
        info = org_info.get(org_id, {}) if org_id is not None else {}
        items.append(
            {
                "id": int(user.id),
                "name": (user.name or "").strip() or (user.phone or ""),
                "phone": user.phone,
                "role": user.role,
                "school_tier": info.get("school_tier") or None,
                "organization_name": info.get("organization_name") or "",
                "member_kind": "enrolled",
                "membership_role": membership.role,
                "initial_password": "",
                "must_change_password": False,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }
        )
    return items
