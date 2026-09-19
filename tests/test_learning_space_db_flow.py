"""Live Postgres: Learning Space create / publish / review / permission / RLS / races."""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import bindparam, select, text
from sqlalchemy.exc import IntegrityError

from models.domain.auth import User
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_ACTIVE,
    ASSIGNMENT_STATUS_DRAFT,
    CLASS_STATUS_ACTIVE,
    CLASS_STATUS_ARCHIVED,
    SUBMISSION_STATUS_RETURNED,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningClass,
    LearningPilotTeacher,
    LearningSubmission,
)
from services.learning_space.access import (
    assert_assignment_visible_to_learner,
    get_class_for_staff,
    get_class_for_teacher,
    get_enabled_pilot,
    require_class_learner,
    require_pilot_teacher,
    resolve_assignment_viewer,
)
from services.learning_space.assignments import (
    get_or_create_submission,
    return_submission,
    save_submission_review,
    submit_assignment,
)
from services.learning_space.class_codes import create_class_with_unique_code
from services.learning_space.memberships import (
    MEMBERSHIP_ROLE_ASSISTANT,
    import_existing_accounts,
    replace_class_assistants,
)
from services.learning_space.students import import_students
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from utils.auth.password import hash_password
from utils.auth.role_constants import ROLE_TEACHER
from utils.db.rls_context import RlsContext, rls_async_session

mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
        reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
    ),
]

_MARK = "ZZLSHW"
_EMAIL_SUFFIX = "@test.learning.local"


class _FakeDiagramCache:
    """In-memory diagram cache so homework open/submit does not need Redis."""

    def __init__(self) -> None:
        self.store: dict[tuple[int, str], dict[str, Any]] = {}
        self.n = 0

    async def get_diagram(self, user_id: int, diagram_id: str) -> dict[str, Any] | None:
        """Return a stored diagram payload."""
        return self.store.get((int(user_id), str(diagram_id)))

    async def save_diagram(self, **kwargs: Any) -> tuple[bool, str, None]:
        """Store a new diagram and return its id."""
        self.n += 1
        new_id = str(kwargs.get("diagram_id") or f"zzls-{self.n}-{uuid.uuid4().hex[:8]}")
        owner = int(kwargs["user_id"])
        self.store[(owner, new_id)] = {
            "title": kwargs.get("title"),
            "diagram_type": kwargs.get("diagram_type") or "mind_map",
            "spec": kwargs.get("spec") or {"topic": "t", "children": []},
            "language": kwargs.get("language") or "zh",
            "thumbnail": kwargs.get("thumbnail"),
        }
        return True, new_id, None

    async def update_diagram_meta_only(
        self,
        user_id: int,
        diagram_id: str,
        title: str,
        thumbnail: str | None,
    ) -> None:
        """Rename a stored diagram without rewriting the spec."""
        row = self.store.get((int(user_id), str(diagram_id)))
        if row is not None:
            row["title"] = title
            row["thumbnail"] = thumbnail


def _sys() -> RlsContext:
    return RlsContext(mode="system")


def _auth(user_id: int, organization_id: int) -> RlsContext:
    return RlsContext(mode="authenticated", user_id=user_id, organization_id=organization_id)


async def _two_orgs() -> tuple[int, int]:
    async with rls_async_session(_sys()) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT organization_id FROM users "
                    "WHERE organization_id IS NOT NULL ORDER BY organization_id LIMIT 2"
                )
            )
        ).all()
    if len(rows) < 2:
        pytest.skip("need users in two organizations")
    return int(rows[0][0]), int(rows[1][0])


async def _make_user(session, *, org_id: int, tag: str) -> User:
    user = User(
        email=f"{_MARK}.{tag}.{uuid.uuid4().hex[:10]}{_EMAIL_SUFFIX}",
        phone=None,
        name=f"{_MARK} {tag}",
        password_hash=hash_password("ZzLsHw123"),
        role=ROLE_TEACHER,
        organization_id=org_id,
        login_password_set=True,
        must_change_password=False,
    )
    session.add(user)
    await session.flush()
    return user


async def _cleanup() -> None:
    async with rls_async_session(_sys()) as session:
        class_ids = [
            int(cid)
            for (cid,) in (
                await session.execute(
                    text("SELECT id FROM learning_classes WHERE name LIKE :p OR class_code LIKE :c"),
                    {"p": f"{_MARK}%", "c": f"{_MARK}%"},
                )
            ).all()
        ]
        if class_ids:
            student_ids = [
                int(uid)
                for (uid,) in (
                    await session.execute(
                        text("SELECT id FROM users WHERE learning_class_id IN :ids").bindparams(
                            bindparam("ids", expanding=True)
                        ),
                        {"ids": class_ids},
                    )
                ).all()
            ]
            await session.execute(
                text("DELETE FROM learning_classes WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": class_ids},
            )
            if student_ids:
                await session.execute(
                    text("DELETE FROM users WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
                    {"ids": student_ids},
                )
        await session.execute(
            text(
                "DELETE FROM learning_pilot_teachers WHERE teacher_user_id IN "
                "(SELECT id FROM users WHERE email LIKE :e)"
            ),
            {"e": f"{_MARK}.%{_EMAIL_SUFFIX}"},
        )
        await session.execute(
            text("DELETE FROM users WHERE email LIKE :e"),
            {"e": f"{_MARK}.%{_EMAIL_SUFFIX}"},
        )
        await session.commit()


@asynccontextmanager
async def _learning_space_world(monkeypatch: pytest.MonkeyPatch):
    """Throwaway teacher / assistant / outsider, two schools, fake diagram cache."""
    await _cleanup()
    org_a, org_b = await _two_orgs()
    cache = _FakeDiagramCache()
    monkeypatch.setattr("services.learning_space.assignments.get_diagram_cache", lambda: cache)
    async with rls_async_session(_sys()) as session:
        teacher = await _make_user(session, org_id=org_a, tag="teacher")
        assistant = await _make_user(session, org_id=org_a, tag="assistant")
        outsider = await _make_user(session, org_id=org_b, tag="outsider")
        session.add(
            LearningPilotTeacher(
                teacher_user_id=int(teacher.id),
                organization_id=org_a,
                enabled=True,
                created_by=int(teacher.id),
            )
        )
        await session.commit()
        ids = SimpleNamespace(
            org_a=org_a,
            org_b=org_b,
            teacher_id=int(teacher.id),
            assistant_id=int(assistant.id),
            outsider_id=int(outsider.id),
        )
    try:
        yield ids
    finally:
        await _cleanup()


async def test_create_class_publish_homework_review_return(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teacher creates a class, publishes homework, student submits, teacher reviews."""
    async with _learning_space_world(monkeypatch) as world:
        await _run_create_class_publish_homework_review_return(world)


async def _run_create_class_publish_homework_review_return(world: SimpleNamespace) -> None:
    async with rls_async_session(_sys()) as session:
        teacher = await session.get(User, world.teacher_id)
        assert teacher is not None
        cls = await create_class_with_unique_code(
            session,
            name=f"{_MARK} class",
            teacher_user_id=int(teacher.id),
            organization_id=world.org_a,
            class_status=CLASS_STATUS_ACTIVE,
            max_students=20,
        )
        imported = await import_students(session, cls, ["张三测"])
        assert len(imported.created) == 1
        student_id = int(imported.created[0]["id"])
        class_id = int(cls.id)

    async with rls_async_session(_sys()) as session:
        student = await session.get(User, student_id)
        assert student is not None
        with pytest.raises(HTTPException) as locked:
            await require_class_learner(session, student, class_id)
        assert locked.value.status_code == 403
        assert "Password" in str(locked.value.detail)
        student.must_change_password = False
        await session.commit()

    async with rls_async_session(_auth(world.teacher_id, world.org_a)) as session:
        teacher = await session.get(User, world.teacher_id)
        assert teacher is not None
        await require_pilot_teacher(session, teacher)
        owned = await get_class_for_teacher(session, class_id, world.teacher_id)
        assignment = LearningAssignment(
            class_id=class_id,
            title=f"{_MARK} homework",
            instructions="画一张图",
            template_diagram_id="template-zzls",
            ai_permissions={"template_role": "none", "diagram_type": "mind_map"},
            instruction_images=[],
            organization_id=world.org_a,
            created_by=world.teacher_id,
            status=ASSIGNMENT_STATUS_ACTIVE,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        assignment_id = int(assignment.id)
        assert int(owned.id) == class_id

    async with rls_async_session(_auth(student_id, world.org_a)) as session:
        student = await session.get(User, student_id)
        assignment = await session.get(LearningAssignment, assignment_id)
        assert student is not None and assignment is not None
        await require_class_learner(session, student, class_id)
        viewer = await resolve_assignment_viewer(session, student, assignment)
        assert viewer == "learner"
        submission = await get_or_create_submission(
            session,
            assignment,
            student,
            organization_id=world.org_a,
        )
        assert submission.status != SUBMISSION_STATUS_SUBMITTED
        submitted = await submit_assignment(session, assignment, student)
        assert submitted.status == SUBMISSION_STATUS_SUBMITTED
        submission_id = int(submitted.id)

    async with rls_async_session(_auth(world.teacher_id, world.org_a)) as session:
        teacher = await session.get(User, world.teacher_id)
        assignment = await session.get(LearningAssignment, assignment_id)
        submission = await session.get(LearningSubmission, submission_id)
        assert teacher is not None and assignment is not None and submission is not None
        assert await resolve_assignment_viewer(session, teacher, assignment) == "staff"
        reviewed = await save_submission_review(
            session,
            submission,
            scores={"理解": 4, "应用": 5},
            comment="写得清楚",
            liked=True,
            pinned=True,
        )
        assert reviewed.review_liked is True
        assert reviewed.review_pinned is True
        assert reviewed.review_scores == {"理解": 4, "应用": 5}
        returned = await return_submission(session, reviewed)
        assert returned.status == SUBMISSION_STATUS_RETURNED


async def test_permissions_assistant_outsider_draft_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assistants review only; outsiders and drafts are rejected; archive blocks learners."""
    async with _learning_space_world(monkeypatch) as world:
        await _test_permissions_assistant_outsider_draft_archive(world)


async def _test_permissions_assistant_outsider_draft_archive(world: SimpleNamespace) -> None:
    async with rls_async_session(_sys()) as session:
        teacher = await session.get(User, world.teacher_id)
        assistant = await session.get(User, world.assistant_id)
        assert teacher is not None and assistant is not None
        cls = await create_class_with_unique_code(
            session,
            name=f"{_MARK} perm",
            teacher_user_id=int(teacher.id),
            organization_id=world.org_a,
            class_status=CLASS_STATUS_ACTIVE,
            max_students=20,
        )
        await replace_class_assistants(session, cls, [world.assistant_id])
        imported = await import_students(session, cls, ["李四测"])
        student_id = int(imported.created[0]["id"])
        student = await session.get(User, student_id)
        assert student is not None
        student.must_change_password = False
        draft = LearningAssignment(
            class_id=int(cls.id),
            title=f"{_MARK} draft",
            instructions="",
            template_diagram_id="template-zzls",
            organization_id=world.org_a,
            created_by=world.teacher_id,
            status=ASSIGNMENT_STATUS_DRAFT,
        )
        published = LearningAssignment(
            class_id=int(cls.id),
            title=f"{_MARK} published",
            instructions="",
            template_diagram_id="template-zzls",
            organization_id=world.org_a,
            created_by=world.teacher_id,
            status=ASSIGNMENT_STATUS_ACTIVE,
        )
        session.add_all([draft, published])
        await session.commit()
        class_id = int(cls.id)
        draft_id = int(draft.id)
        published_id = int(published.id)

    async with rls_async_session(_auth(world.assistant_id, world.org_a)) as session:
        assistant = await session.get(User, world.assistant_id)
        assert assistant is not None
        staff = await get_class_for_staff(session, class_id, world.assistant_id)
        assert int(staff.id) == class_id
        with pytest.raises(HTTPException) as not_owner:
            await get_class_for_teacher(session, class_id, world.assistant_id)
        assert not_owner.value.status_code == 404
        with pytest.raises(HTTPException) as not_pilot:
            await require_pilot_teacher(session, assistant)
        assert not_pilot.value.status_code == 403
        published = await session.get(LearningAssignment, published_id)
        draft = await session.get(LearningAssignment, draft_id)
        assert published is not None and draft is not None
        assert await resolve_assignment_viewer(session, assistant, published) == "staff"
        assert await resolve_assignment_viewer(session, assistant, draft) == "staff"

    async with rls_async_session(_auth(world.outsider_id, world.org_b)) as session:
        outsider = await session.get(User, world.outsider_id)
        published = await session.get(LearningAssignment, published_id)
        assert outsider is not None
        with pytest.raises(HTTPException):
            await get_class_for_staff(session, class_id, world.outsider_id)
        if published is not None:
            with pytest.raises(HTTPException):
                await resolve_assignment_viewer(session, outsider, published)

    async with rls_async_session(_auth(student_id, world.org_a)) as session:
        student = await session.get(User, student_id)
        draft = await session.get(LearningAssignment, draft_id)
        published = await session.get(LearningAssignment, published_id)
        assert student is not None and draft is not None and published is not None
        with pytest.raises(HTTPException) as hidden:
            assert_assignment_visible_to_learner(draft)
        assert hidden.value.status_code == 404
        with pytest.raises(HTTPException) as draft_open:
            await resolve_assignment_viewer(session, student, draft)
        assert draft_open.value.status_code == 404
        assert await resolve_assignment_viewer(session, student, published) == "learner"

    async with rls_async_session(_sys()) as session:
        cls = await session.get(LearningClass, class_id)
        assert cls is not None
        cls.status = CLASS_STATUS_ARCHIVED
        await session.commit()

    async with rls_async_session(_auth(student_id, world.org_a)) as session:
        student = await session.get(User, student_id)
        assert student is not None
        with pytest.raises(HTTPException) as archived:
            await require_class_learner(session, student, class_id)
        assert archived.value.status_code == 403

    async with rls_async_session(_sys()) as session:
        pilot = await get_enabled_pilot(session, world.teacher_id)
        assert pilot is not None
        pilot.enabled = False
        await session.commit()

    async with rls_async_session(_auth(world.teacher_id, world.org_a)) as session:
        with pytest.raises(HTTPException) as disabled:
            await get_class_for_staff(session, class_id, world.teacher_id, allow_archived=True)
        assert disabled.value.status_code == 404
        staff = await get_class_for_staff(session, class_id, world.assistant_id, allow_archived=True)
        assert int(staff.id) == class_id


async def test_rls_other_school_cannot_see_class(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authenticated teacher in school B cannot read school A's class or homework."""
    async with _learning_space_world(monkeypatch) as world:
        await _test_rls_other_school_cannot_see_class(world)


async def _test_rls_other_school_cannot_see_class(world: SimpleNamespace) -> None:
    async with rls_async_session(_sys()) as session:
        teacher = await session.get(User, world.teacher_id)
        assert teacher is not None
        cls = await create_class_with_unique_code(
            session,
            name=f"{_MARK} rls",
            teacher_user_id=int(teacher.id),
            organization_id=world.org_a,
            class_status=CLASS_STATUS_ACTIVE,
            max_students=10,
        )
        session.add(
            LearningAssignment(
                class_id=int(cls.id),
                title=f"{_MARK} rls hw",
                instructions="",
                template_diagram_id="template-zzls",
                organization_id=world.org_a,
                created_by=world.teacher_id,
                status=ASSIGNMENT_STATUS_ACTIVE,
            )
        )
        await session.commit()
        class_id = int(cls.id)

    async with rls_async_session(_auth(world.teacher_id, world.org_a)) as session:
        seen = (
            await session.execute(select(LearningClass.id).where(LearningClass.id == class_id))
        ).scalar_one_or_none()
        hw = (
            (await session.execute(select(LearningAssignment.title).where(LearningAssignment.class_id == class_id)))
            .scalars()
            .all()
        )
        assert seen == class_id
        assert hw == [f"{_MARK} rls hw"]

    async with rls_async_session(_auth(world.outsider_id, world.org_b)) as session:
        hidden_class = (
            await session.execute(select(LearningClass.id).where(LearningClass.id == class_id))
        ).scalar_one_or_none()
        hidden_hw = (
            (await session.execute(select(LearningAssignment.title).where(LearningAssignment.class_id == class_id)))
            .scalars()
            .all()
        )
        assert hidden_class is None
        assert hidden_hw == []

    async with rls_async_session(RlsContext.deny_default()) as session:
        locked = (
            await session.execute(select(LearningClass.id).where(LearningClass.id == class_id))
        ).scalar_one_or_none()
        assert locked is None


async def test_class_code_unique_race(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two inserts of the same class_code: one commit, one IntegrityError."""
    async with _learning_space_world(monkeypatch) as world:
        await _test_class_code_unique_race(world)


async def _test_class_code_unique_race(world: SimpleNamespace) -> None:
    code = f"{_MARK}RACE"

    async def _try_insert(teacher_id: int, org_id: int) -> bool:
        async with rls_async_session(_sys()) as session:
            session.add(
                LearningClass(
                    name=f"{_MARK} race",
                    class_code=code,
                    teacher_user_id=teacher_id,
                    organization_id=org_id,
                    status=CLASS_STATUS_ACTIVE,
                    max_students=10,
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    won = await asyncio.gather(
        _try_insert(world.teacher_id, world.org_a),
        _try_insert(world.teacher_id, world.org_a),
    )
    assert won.count(True) == 1
    assert won.count(False) == 1


async def test_submission_unique_race(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent open of the same homework collapses to one submission row."""
    async with _learning_space_world(monkeypatch) as world:
        await _test_submission_unique_race(world)


async def _test_submission_unique_race(world: SimpleNamespace) -> None:
    async with rls_async_session(_sys()) as session:
        teacher = await session.get(User, world.teacher_id)
        assert teacher is not None
        cls = await create_class_with_unique_code(
            session,
            name=f"{_MARK} subrace",
            teacher_user_id=int(teacher.id),
            organization_id=world.org_a,
            class_status=CLASS_STATUS_ACTIVE,
            max_students=10,
        )
        imported = await import_students(session, cls, ["王五测"])
        student_id = int(imported.created[0]["id"])
        student = await session.get(User, student_id)
        assert student is not None
        student.must_change_password = False
        assignment = LearningAssignment(
            class_id=int(cls.id),
            title=f"{_MARK} race hw",
            instructions="",
            template_diagram_id="template-zzls",
            ai_permissions={"template_role": "none", "diagram_type": "mind_map"},
            organization_id=world.org_a,
            created_by=world.teacher_id,
            status=ASSIGNMENT_STATUS_ACTIVE,
        )
        session.add(assignment)
        await session.commit()
        assignment_id = int(assignment.id)

    async def _open() -> int:
        async with rls_async_session(_auth(student_id, world.org_a)) as session:
            student = await session.get(User, student_id)
            assignment = await session.get(LearningAssignment, assignment_id)
            assert student is not None and assignment is not None
            row = await get_or_create_submission(
                session,
                assignment,
                student,
                organization_id=world.org_a,
            )
            return int(row.id)

    first, second = await asyncio.gather(_open(), _open())
    assert first == second
    async with rls_async_session(_sys()) as session:
        count = (
            await session.execute(
                select(LearningSubmission.id).where(LearningSubmission.assignment_id == assignment_id)
            )
        ).all()
        assert len(count) == 1


async def test_imported_account_cannot_be_class_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Class owner cannot be imported as a learner."""
    async with _learning_space_world(monkeypatch) as world:
        await _test_imported_account_cannot_be_class_teacher(world)


async def _test_imported_account_cannot_be_class_teacher(world: SimpleNamespace) -> None:
    async with rls_async_session(_sys()) as session:
        teacher = await session.get(User, world.teacher_id)
        assert teacher is not None
        teacher.phone = f"199{uuid.uuid4().int % 10**8:08d}"
        cls = await create_class_with_unique_code(
            session,
            name=f"{_MARK} import",
            teacher_user_id=int(teacher.id),
            organization_id=world.org_a,
            class_status=CLASS_STATUS_ACTIVE,
            max_students=10,
        )
        await session.commit()
        result = await import_existing_accounts(session, cls, [str(teacher.phone)])
        assert result["created"] == []
        assert result["failed"][0]["error"] == "is_class_teacher"
        assistant = await session.get(User, world.assistant_id)
        assert assistant is not None
        assistant.phone = f"198{uuid.uuid4().int % 10**8:08d}"
        await session.commit()
        enrolled = await import_existing_accounts(session, cls, [str(assistant.phone)])
        assert len(enrolled["created"]) == 1
        await replace_class_assistants(session, cls, [world.assistant_id])
        await session.commit()
        role = (
            await session.execute(
                text("SELECT role FROM learning_class_memberships WHERE class_id = :c AND user_id = :u"),
                {"c": int(cls.id), "u": world.assistant_id},
            )
        ).scalar_one()
        assert role == MEMBERSHIP_ROLE_ASSISTANT
