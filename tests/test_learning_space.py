"""Unit tests for Learning Space helpers and AI gate.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from models.domain.auth import User
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_ACTIVE,
    ASSIGNMENT_STATUS_DRAFT,
    SUBMISSION_STATUS_DRAFT,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningClass,
    LearningSubmission,
)
from routers.features.learning_space.deps import (
    bind_superadmin_learning_space_rls,
    pin_superadmin_learning_space_rls,
)
from routers.features.learning_space.schemas import ClassUpdate
from services.diagram.semantic_spec_validation import validate_semantic_spec
from services.learning_space.access import (
    assert_assignment_visible_to_learner,
    classes_visible_to_staff,
    get_class_for_staff,
    require_pilot_teacher,
)
from services.learning_space.staff_overview import assignment_metric_rows
from services.learning_space.assignments import (
    apply_learner_due,
    assert_can_edit_submission,
    student_homework_diagram_title,
    student_open_diagram_payload,
    submission_allows_resubmit,
    _normalize_preview_spec,
    _resolve_submission_diagram_fields,
    _resolve_submission_org_id,
)
from services.learning_space.admin_teachers import (
    assert_teacher_eligible_for_pilot,
)
from services.learning_space.blank_spec import blank_spec_for_type, resolve_template_role
from services.learning_space.memberships import normalize_account_phone, parse_account_phones
from services.learning_space.students import remove_class_member
from services.learning_space.passwords import (
    ai_permission_allowed,
    generate_class_code,
    initial_password_from_name,
    merge_ai_permissions,
    normalize_student_name,
    staff_visible_learning_space_password,
)
from services.learning_space.synthetic_email import (
    is_learning_space_synthetic_email,
    student_synthetic_email,
)
from services.learning_space.students import preview_student_names
from tests.typing_helpers import as_type, as_user
from utils.auth.admin_panel_permissions import can_manage_learning_space_classes
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.db.rls_context import RlsContext
from utils.db.rls_types import MODE_PANEL_SUPERADMIN


def test_assert_teacher_eligible_rejects_student() -> None:
    """Reject classroom students as Learning Space pilots."""
    with pytest.raises(ValueError, match="Students cannot"):
        assert_teacher_eligible_for_pilot(as_user(SimpleNamespace(role="student", organization_id=1)), 1)


def test_assert_teacher_eligible_rejects_org_mismatch() -> None:
    """Reject pilots whose organization does not match the class school."""
    with pytest.raises(ValueError, match="Organization"):
        assert_teacher_eligible_for_pilot(as_user(SimpleNamespace(role="school_admin", organization_id=2)), 1)


def test_assert_teacher_eligible_ok_for_school_admin() -> None:
    """Allow school admins in the same organization to become pilots."""
    assert_teacher_eligible_for_pilot(as_user(SimpleNamespace(role="school_admin", organization_id=3)), 3)


def test_assert_teacher_eligible_ok_for_legacy_user_role() -> None:
    """Allow the legacy user role to become a pilot in the same org."""
    assert_teacher_eligible_for_pilot(as_user(SimpleNamespace(role="user", organization_id=3)), 3)


@pytest.mark.parametrize(
    "role",
    [
        "superadmin",
        "school_admin",
        "teacher",
        "user",  # legacy → school edition teacher
        "personal_trial",  # 体验版
        "personal_paid",  # 超级会员
    ],
)
def test_assert_teacher_eligible_ok_for_platform_identities(role: str) -> None:
    """Any non-student platform identity with matching org can become a pilot teacher."""
    assert_teacher_eligible_for_pilot(as_user(SimpleNamespace(role=role, organization_id=9)), 9)


def test_assert_teacher_eligible_rejects_missing_org() -> None:
    """Reject accounts that are not attached to an organization."""
    with pytest.raises(ValueError, match="no organization"):
        assert_teacher_eligible_for_pilot(as_user(SimpleNamespace(role="personal_paid", organization_id=None)), 1)


@pytest.mark.parametrize("role", ["superadmin", "platform_bd", "expert", "school_admin"])
def test_can_manage_learning_space_classes_for_panel_roles(role: str) -> None:
    """The four panel roles may create Learning Space classes in admin."""
    assert can_manage_learning_space_classes(as_user(SimpleNamespace(role=role))) is True


def test_can_manage_learning_space_classes_rejects_teacher() -> None:
    """Teachers create classes only after an admin enables them as a pilot."""
    assert can_manage_learning_space_classes(as_user(SimpleNamespace(role="teacher"))) is False


def test_initial_password_from_chinese_name() -> None:
    """Derive the default student password from pinyin initials."""
    assert initial_password_from_name("张三") == "zs123"


def test_staff_visible_password_only_while_change_required() -> None:
    """Roster shows the temporary password until the student sets their own."""
    assert (
        staff_visible_learning_space_password(
            name="张三",
            role="student",
            learning_class_id=3,
            must_change_password=False,
            stored_password="mySecret9",
        )
        == ""
    )
    assert (
        staff_visible_learning_space_password(
            name="张三",
            role="student",
            learning_class_id=3,
            must_change_password=True,
            stored_password="tempPass1",
        )
        == "tempPass1"
    )
    assert (
        staff_visible_learning_space_password(
            name="张三",
            role="student",
            learning_class_id=3,
            must_change_password=True,
            stored_password=None,
        )
        == "zs123"
    )


def test_apply_learner_due_uses_personal_override() -> None:
    """A per-student extension replaces the class deadline on that student's payload."""
    assignment = cast(LearningAssignment, SimpleNamespace(due_at=datetime(2020, 1, 1, tzinfo=UTC)))
    submission = cast(LearningSubmission, SimpleNamespace(due_at_override=datetime(2030, 6, 1, tzinfo=UTC)))
    payload = apply_learner_due({}, assignment, submission)
    assert payload["due_at"] is not None
    assert payload["due_at"].startswith("2030-06-01")


def test_synthetic_student_email_is_not_a_real_login() -> None:
    """Placeholder emails stay out of email-login GeoIP without importing pypinyin."""
    assert student_synthetic_email(23, 4830) == "s23.4830@student.learning.local"
    assert is_learning_space_synthetic_email("s23.4830@student.learning.local")
    assert is_learning_space_synthetic_email("  S23.4830@STUDENT.LEARNING.LOCAL  ")
    assert not is_learning_space_synthetic_email("teacher@school.edu")
    assert not is_learning_space_synthetic_email(None)


def test_normalize_and_preview_rejects_duplicate_names() -> None:
    """Normalize names and flag duplicates in an import preview."""
    assert normalize_student_name("  张  三 ") == "张 三"
    rows = preview_student_names(["张三", "张三", "李四"])
    assert rows[0].ok is True
    assert rows[1].ok is False
    assert rows[1].error == "duplicate_name_in_file"
    assert rows[2].ok is True
    assert rows[2].initial_password == initial_password_from_name("李四")


def test_class_code_alphabet_excludes_ambiguous() -> None:
    """Omit ambiguous characters from generated class codes."""
    code = generate_class_code(12)
    assert len(code) == 12
    assert "0" not in code
    assert "O" not in code
    assert "I" not in code
    assert "1" not in code


def test_class_update_normalizes_alnum_code() -> None:
    """Uppercase alphanumeric class codes and reject invalid ones."""
    updated = ClassUpdate.model_validate({"class_code": "ab12cd"})
    assert updated.class_code == "AB12CD"
    with pytest.raises(ValidationError):
        ClassUpdate.model_validate({"class_code": "AB-12"})
    with pytest.raises(ValidationError):
        ClassUpdate.model_validate({"class_code": "AB"})


def test_merge_ai_permissions_defaults() -> None:
    """Fill AI permission defaults and drop unknown keys."""
    merged = merge_ai_permissions({"node_palette": True, "unknown": True})
    assert merged["ai_assist"] is True
    assert merged["ai_brainstorm"] is True
    assert merged["node_palette"] is True
    assert merged["topic_generate"] is False
    assert merged["generate_diagram"] is False
    assert merged["allow_resubmit"] is True
    assert "unknown" not in merged
    typed = merge_ai_permissions({"diagram_type": "bridge_map", "has_teacher_template": False, "ai_assist": False})
    assert typed["diagram_type"] == "bridge_map"
    assert typed["has_teacher_template"] is False
    assert ai_permission_allowed(merged, "ai_brainstorm") is True
    assert ai_permission_allowed(merged, "node_palette") is True
    assert ai_permission_allowed(merged, "topic_generate") is False
    assert ai_permission_allowed(merged, "generate_diagram") is False


def test_merge_ai_assist_master_switch_off() -> None:
    """Turn off granular AI tools when the master assist switch is off."""
    merged = merge_ai_permissions({"ai_assist": False, "topic_generate": True, "ai_brainstorm": True})
    assert merged["ai_assist"] is False
    assert merged["topic_generate"] is False
    assert merged["ai_brainstorm"] is False
    assert ai_permission_allowed(merged, "topic_generate") is False


def test_student_ai_gate_permission_matrix() -> None:
    """Map legacy capability aliases onto merged assignment permissions."""
    perms = merge_ai_permissions({"ai_assist": True, "ai_brainstorm": True, "topic_generate": False})
    assert ai_permission_allowed(perms, "ai_brainstorm") is True
    assert ai_permission_allowed(perms, "node_palette") is True
    assert ai_permission_allowed(perms, "topic_generate") is False
    assert ai_permission_allowed(perms, "generate_diagram") is False
    assert ai_permission_allowed(perms, "inline_recommend") is True


def test_ai_assist_master_off_blocks_conversational_edit() -> None:
    """Master ai_assist switch disables conversational edit even when granular flag set."""
    merged = merge_ai_permissions({"ai_assist": False, "conversational_edit": True})
    assert merged["conversational_edit"] is False
    assert ai_permission_allowed(merged, "conversational_edit") is False


def test_assert_can_edit_past_due() -> None:
    """Block edits after the assignment due time."""
    assignment = LearningAssignment(
        class_id=1,
        title="t",
        instructions="",
        template_diagram_id="d1",
        due_at=datetime.now(UTC) - timedelta(hours=1),
        ai_permissions={},
        created_by=1,
        status=ASSIGNMENT_STATUS_ACTIVE,
    )
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        status=SUBMISSION_STATUS_DRAFT,
    )
    with pytest.raises(HTTPException) as exc:
        assert_can_edit_submission(assignment, submission)
    assert exc.value.status_code == 400
    assert "Past due" in str(exc.value.detail)


def test_draft_assignment_hidden_from_learners() -> None:
    """Students must not open unpublished homework by guessing the id."""
    assignment = LearningAssignment(
        class_id=1,
        title="t",
        instructions="",
        template_diagram_id="d1",
        created_by=1,
        organization_id=3,
        status=ASSIGNMENT_STATUS_DRAFT,
    )
    with pytest.raises(HTTPException) as exc:
        assert_assignment_visible_to_learner(assignment)
    assert exc.value.status_code == 404


def test_published_assignment_visible_to_learners() -> None:
    """Active homework is visible to class learners."""
    assignment = LearningAssignment(
        class_id=1,
        title="t",
        instructions="",
        template_diagram_id="d1",
        created_by=1,
        organization_id=3,
        status=ASSIGNMENT_STATUS_ACTIVE,
    )
    assert_assignment_visible_to_learner(assignment)


def test_assert_can_edit_already_submitted() -> None:
    """Block edits once a submission is already submitted."""
    assignment = LearningAssignment(
        class_id=1,
        title="t",
        instructions="",
        template_diagram_id="d1",
        due_at=None,
        ai_permissions={"allow_resubmit": False},
        created_by=1,
        status=ASSIGNMENT_STATUS_ACTIVE,
    )
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        status=SUBMISSION_STATUS_SUBMITTED,
    )
    with pytest.raises(HTTPException) as exc:
        assert_can_edit_submission(assignment, submission)
    assert "Already submitted" in str(exc.value.detail)


def test_assert_can_edit_allows_resubmit_before_due() -> None:
    """Allow edits while resubmit is enabled and the deadline has not passed."""
    assignment = LearningAssignment(
        class_id=1,
        title="t",
        instructions="",
        template_diagram_id="d1",
        due_at=None,
        ai_permissions={},
        created_by=1,
        status=ASSIGNMENT_STATUS_ACTIVE,
    )
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        status=SUBMISSION_STATUS_SUBMITTED,
    )
    assert submission_allows_resubmit(assignment, submission) is True
    assert_can_edit_submission(assignment, submission)


def test_merge_copies_reference_diagrams() -> None:
    """Keep unique reference diagram entries when merging permissions."""
    merged = merge_ai_permissions(
        {
            "ai_assist": False,
            "reference_diagrams": [
                {"id": "d1", "title": "对照 A", "thumbnail": "https://cdn.example/a.png"},
                {"id": "d1", "title": "dup"},
                {"id": "", "title": "skip"},
                "bad",
            ],
        }
    )
    assert merged["reference_diagrams"] == [
        {"id": "d1", "title": "对照 A", "thumbnail": "https://cdn.example/a.png"},
    ]


def test_merge_keeps_template_thumbnail_ref() -> None:
    """COS thumbnail refs survive permission merge; other strings do not."""
    merged = merge_ai_permissions(
        {
            "ai_assist": False,
            "template_thumbnail_ref": "lsimg:4/2026/10/thumb.png",
        }
    )
    assert merged["template_thumbnail_ref"] == "lsimg:4/2026/10/thumb.png"
    dropped = merge_ai_permissions({"template_thumbnail_ref": "data:image/png;base64,aaaa"})
    assert "template_thumbnail_ref" not in dropped


def test_merge_copies_template_role() -> None:
    """Preserve template role and start mode on merged permissions."""
    merged = merge_ai_permissions(
        {
            "ai_assist": False,
            "diagram_type": "bridge_map",
            "template_role": "reference",
        }
    )
    assert merged["template_role"] == "reference"
    assert merged["start_mode"] == "blank"
    assert merged["has_teacher_template"] is True


def test_resolve_template_role_legacy() -> None:
    """Infer template role from legacy has_teacher_template flags."""
    assert resolve_template_role({"has_teacher_template": False}) == "none"
    assert resolve_template_role({"has_teacher_template": True}) == "scaffold"
    assert resolve_template_role({}) == "scaffold"
    assert resolve_template_role({"template_role": "reference"}) == "reference"


def test_blank_specs_are_semantically_valid() -> None:
    """Ensure blank homework specs validate for each diagram type."""
    types = [
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "mind_map",
        "concept_map",
        "mindmap",
    ]
    for dtype in types:
        spec = blank_spec_for_type("单元练习", dtype)
        ok, issues, _normalized = validate_semantic_spec(dtype, spec)
        assert ok, f"{dtype}: {issues}"


def test_blank_specs_ignore_assignment_title() -> None:
    """Blank homework specs use default canvas labels, not the assignment title."""
    spec = blank_spec_for_type("桥形图练习", "mind_map")
    assert spec["topic"] == "中心主题"
    assert "桥形图练习" not in str(spec)


def test_student_open_reference_uses_blank_not_teacher_spec() -> None:
    """Open reference homework from a blank spec instead of the teacher map."""
    assignment = as_type(
        SimpleNamespace(
            title="桥形图练习",
            ai_permissions={
                "diagram_type": "bridge_map",
                "template_role": "reference",
                "has_teacher_template": True,
            },
        ),
        LearningAssignment,
    )

    teacher_spec = {
        "relating_factor": "如同",
        "analogies": [{"left": "鸟", "right": "飞机"}],
    }
    template = {"diagram_type": "bridge_map", "spec": teacher_spec, "language": "zh"}
    dtype, spec, _lang, thumb = student_open_diagram_payload(assignment, template)
    assert dtype == "bridge_map"
    assert spec != teacher_spec
    assert spec["analogies"][0]["left"] == "事物A1"
    assert spec["relating_factor"] == "[点击设置]"
    assert thumb is None


def test_student_open_scaffold_clones_teacher_spec() -> None:
    """Clone the teacher spec when homework starts as a scaffold."""
    assignment = as_type(
        SimpleNamespace(
            title="补全",
            ai_permissions={
                "diagram_type": "bubble_map",
                "template_role": "scaffold",
                "has_teacher_template": True,
            },
        ),
        LearningAssignment,
    )

    teacher_spec = {"topic": "狮子", "attributes": ["鬃毛"]}
    template = {
        "diagram_type": "bubble_map",
        "spec": teacher_spec,
        "language": "zh",
        "thumbnail": "data:image/png;base64,xx",
    }
    dtype, spec, lang, thumb = student_open_diagram_payload(assignment, template)
    assert dtype == "bubble_map"
    assert spec == teacher_spec
    assert lang == "zh"
    assert thumb == "data:image/png;base64,xx"


def test_student_homework_diagram_title() -> None:
    """Build student diagram titles from name or user id."""
    assert student_homework_diagram_title("张三", 9, "桥形图练习") == "张三_桥形图练习"
    assert student_homework_diagram_title("  ", 9, "作业A") == "9_作业A"


def test_parse_account_phones_dedupes() -> None:
    """Normalize phone numbers and drop duplicates on import."""
    assert normalize_account_phone(" 138-0013-8000 ") == "13800138000"
    phones = parse_account_phones("13800138000\n13800138000\n13900139000")
    assert phones == ["13800138000", "13900139000"]


def _staff_class() -> SimpleNamespace:
    return SimpleNamespace(id=1, teacher_user_id=9, status="active")


@pytest.mark.asyncio
async def test_staff_owner_requires_enabled_pilot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled or missing pilots cannot review as class owner."""
    db = AsyncMock()
    db.get = AsyncMock(return_value=_staff_class())
    monkeypatch.setattr("services.learning_space.access.get_enabled_pilot", AsyncMock(return_value=None))
    monkeypatch.setattr("services.learning_space.access.is_class_assistant", AsyncMock(return_value=False))
    with pytest.raises(HTTPException) as exc:
        await get_class_for_staff(db, 1, 9)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_staff_owner_with_pilot_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enabled pilots may review classes they own."""
    learning_class = _staff_class()
    db = AsyncMock()
    db.get = AsyncMock(return_value=learning_class)
    monkeypatch.setattr(
        "services.learning_space.access.get_enabled_pilot",
        AsyncMock(return_value=SimpleNamespace(id=1)),
    )
    result = await get_class_for_staff(db, 1, 9)
    assert result is learning_class


@pytest.mark.asyncio
async def test_learning_space_rls_bind_is_panel_for_superadmin() -> None:
    """Product routes must open under panel global read before the session queries."""
    request = MagicMock()
    request.state = SimpleNamespace()
    setattr(request.state, AUTH_CONTEXT_USER_ATTR, as_user(SimpleNamespace(id=1, role="superadmin")))
    await bind_superadmin_learning_space_rls(request)
    assert request.state.rls_context.mode == MODE_PANEL_SUPERADMIN
    assert request.state.rls_context.panel_global_read is True


@pytest.mark.asyncio
async def test_learning_space_rls_bind_skips_teacher() -> None:
    """A pilot stays on the authenticated session the middleware already set."""
    request = MagicMock()
    request.state = SimpleNamespace()
    setattr(
        request.state,
        AUTH_CONTEXT_USER_ATTR,
        as_user(SimpleNamespace(id=2, role="teacher", organization_id=9)),
    )
    await bind_superadmin_learning_space_rls(request)
    assert getattr(request.state, "rls_context", None) is None


@pytest.mark.asyncio
async def test_learning_space_db_reapplies_panel_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """SET LOCAL runs on the open transaction so a stale authenticated GUC cannot hide other schools."""
    applied: list[object] = []

    async def _apply(db: object, ctx: object) -> None:
        del db
        applied.append(ctx)

    monkeypatch.setattr("routers.features.learning_space.deps.apply_rls_context_async", _apply)
    user = as_user(SimpleNamespace(id=1, role="superadmin"))
    ctx = RlsContext.panel_superadmin(user)
    request = cast(Request, SimpleNamespace(state=SimpleNamespace(rls_context=ctx)))
    db = AsyncMock()
    await pin_superadmin_learning_space_rls(request, db)
    assert applied == [ctx]


@pytest.mark.asyncio
async def test_superadmin_observes_any_class() -> None:
    """Superadmins may open any class in the teacher shell without being its pilot."""
    learning_class = _staff_class()
    db = AsyncMock()
    db.get = AsyncMock(return_value=learning_class)
    actor = as_user(SimpleNamespace(id=2, role="superadmin"))
    result = await get_class_for_staff(db, 1, 2, actor=actor)
    assert result is learning_class


@pytest.mark.asyncio
async def test_assignment_metric_rows_do_not_load_diagrams() -> None:
    """Overview counts stay in SQL so a superadmin dashboard does not fetch every diagram."""
    due = datetime(2026, 10, 3, tzinfo=UTC)
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(all=lambda: [(7, 3, "作业", "active", due)]),
            SimpleNamespace(all=lambda: [(7, 2)]),
            SimpleNamespace(all=lambda: [(3, 4)]),
            SimpleNamespace(all=lambda: []),
        ]
    )
    rows = await assignment_metric_rows(db, [3])
    assert rows == [
        {
            "id": 7,
            "class_id": 3,
            "title": "作业",
            "status": "active",
            "due_at": due.isoformat(),
            "submitted_count": 2,
            "student_count": 4,
        }
    ]


@pytest.mark.asyncio
async def test_assignment_metric_rows_empty() -> None:
    """No classes means no queries."""
    db = AsyncMock()
    assert await assignment_metric_rows(db, []) == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_superadmin_lists_every_class() -> None:
    """Superadmin class list is not limited to classes they teach or assist."""
    rows = [SimpleNamespace(id=4), SimpleNamespace(id=5)]
    scalars = SimpleNamespace(all=lambda: rows)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: scalars))
    actor = as_user(SimpleNamespace(id=2, role="superadmin"))
    listed = await classes_visible_to_staff(db, actor)
    assert listed == rows


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["platform_bd", "expert", "school_admin"])
async def test_staff_manager_is_not_class_staff(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    """Other panel roles create classes in admin; they are not teacher-API staff."""
    manager = as_user(SimpleNamespace(id=2, role=role))
    assert can_manage_learning_space_classes(manager)
    learning_class = _staff_class()
    db = AsyncMock()
    db.get = AsyncMock(return_value=learning_class)
    monkeypatch.setattr("services.learning_space.access.get_enabled_pilot", AsyncMock(return_value=None))
    monkeypatch.setattr("services.learning_space.access.is_class_assistant", AsyncMock(return_value=False))
    with pytest.raises(HTTPException) as exc:
        await get_class_for_staff(db, 1, 2, actor=manager)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["superadmin", "platform_bd", "expert", "school_admin"])
async def test_require_pilot_teacher_rejects_class_managers(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    """Panel roles cannot publish homework unless they are an enabled pilot."""
    manager = as_user(SimpleNamespace(id=2, role=role))
    monkeypatch.setattr("services.learning_space.access.get_enabled_pilot", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await require_pilot_teacher(AsyncMock(), manager)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_staff_assistant_ok_without_pilot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assistants may review even when they are not pilots."""
    learning_class = _staff_class()
    db = AsyncMock()
    db.get = AsyncMock(return_value=learning_class)
    monkeypatch.setattr("services.learning_space.access.get_enabled_pilot", AsyncMock(return_value=None))
    monkeypatch.setattr("services.learning_space.access.is_class_assistant", AsyncMock(return_value=True))
    result = await get_class_for_staff(db, 1, 8)
    assert result is learning_class


@pytest.mark.asyncio
async def test_remove_class_member_clears_classroom_student(monkeypatch: pytest.MonkeyPatch) -> None:
    """Removing a classroom student clears learning_class_id and ends sessions."""
    learning_class = SimpleNamespace(id=3, teacher_user_id=9)
    student = SimpleNamespace(
        id=11,
        role="student",
        learning_class_id=3,
        phone=None,
        email="s@student.learning.local",
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=student)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    monkeypatch.setattr(
        "services.learning_space.students.user_cache.invalidate",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "services.learning_space.students.revoke_refresh_tokens_and_sessions",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "services.learning_space.students.kick_classroom_student_sessions",
        AsyncMock(),
    )
    result = await remove_class_member(db, cast(LearningClass, learning_class), 11)
    assert result["member_kind"] == "classroom"
    assert student.learning_class_id is None


@pytest.mark.asyncio
async def test_remove_class_member_deletes_enrolled_learner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Removing an enrolled learner deletes the membership row."""
    learning_class = SimpleNamespace(id=3, teacher_user_id=9)
    learner = SimpleNamespace(id=12, role="teacher", learning_class_id=None, phone="13800000000", email="t@x.com")
    membership = SimpleNamespace(id=99, user_id=12, class_id=3, role="learner")
    db = AsyncMock()
    db.get = AsyncMock(return_value=learner)
    execute_result = AsyncMock()
    execute_result.scalar_one_or_none = lambda: membership
    db.execute = AsyncMock(return_value=execute_result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    monkeypatch.setattr(
        "services.learning_space.students.user_cache.invalidate",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "services.learning_space.students.revoke_refresh_tokens_and_sessions",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "services.learning_space.students.kick_classroom_student_sessions",
        AsyncMock(),
    )
    result = await remove_class_member(db, cast(LearningClass, learning_class), 12)
    assert result["member_kind"] == "enrolled"
    db.delete.assert_called_once_with(membership)


def test_resolve_submission_org_id_falls_back_to_submission() -> None:
    """Student wall labels use submission org when user.organization_id is unset."""
    student = SimpleNamespace(id=2, organization_id=None)
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        organization_id=99,
        status=SUBMISSION_STATUS_DRAFT,
    )
    assert _resolve_submission_org_id(cast(User, student), submission) == 99


def test_normalize_preview_spec_unwraps_nested_spec() -> None:
    """Saved diagrams may store a nested spec blob like library flush snapshots."""
    wrapped = {
        "spec": {"topic": "中心主题", "children": []},
        "diagram_type": "mind_map",
    }
    normalized = _normalize_preview_spec(wrapped)
    assert normalized is not None
    assert normalized.get("topic") == "中心主题"


def test_resolve_submission_diagram_fields_prefers_live_draft_spec() -> None:
    """Wall preview can render in-progress homework from the live diagram cache."""
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        diagram_id="diag-1",
        status=SUBMISSION_STATUS_DRAFT,
    )
    diagram = {
        "title": "我的思维导图",
        "diagram_type": "mind_map",
        "spec": {"nodes": [{"id": "topic", "text": "中心主题"}]},
        "thumbnail": "data:image/png;base64,abc",
    }
    thumb, spec, diagram_type, title = _resolve_submission_diagram_fields(submission, diagram)
    assert thumb == "data:image/png;base64,abc"
    assert spec == diagram["spec"]
    assert diagram_type == "mind_map"
    assert title == "我的思维导图"


def test_resolve_submission_diagram_fields_uses_snapshot_when_submitted() -> None:
    """Submitted work keeps the frozen snapshot even if live diagram changes."""
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        diagram_id="diag-1",
        status=SUBMISSION_STATUS_SUBMITTED,
        snapshot_spec={
            "title": "提交版",
            "diagram_type": "bubble_map",
            "spec": {"nodes": [{"id": "topic", "text": "主题"}]},
            "thumbnail": "data:image/png;base64,snap",
        },
    )
    live = {
        "title": "草稿",
        "diagram_type": "mind_map",
        "spec": {"nodes": [{"id": "topic", "text": "草稿"}]},
    }
    thumb, spec, diagram_type, title = _resolve_submission_diagram_fields(submission, live)
    assert thumb == "data:image/png;base64,snap"
    snap = submission.snapshot_spec
    assert isinstance(snap, dict)
    assert spec == snap["spec"]
    assert diagram_type == "bubble_map"
    assert title == "提交版"


def test_resolve_submission_diagram_fields_keeps_live_spec_beside_thumbnail() -> None:
    """A COS thumbnail on the snapshot does not hide the live diagram."""
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        diagram_id="diag-1",
        status=SUBMISSION_STATUS_DRAFT,
        snapshot_spec={"thumbnail": "lsimg:2/2026/10/card.png"},
    )
    live = {
        "title": "作业",
        "diagram_type": "mind_map",
        "spec": {"nodes": [{"id": "topic", "text": "中心"}]},
    }
    thumb, spec, diagram_type, title = _resolve_submission_diagram_fields(submission, live)
    assert thumb == "lsimg:2/2026/10/card.png"
    assert spec == live["spec"]
    assert diagram_type == "mind_map"
    assert title == "作业"


def test_resolve_submission_diagram_fields_keeps_frozen_spec_shape() -> None:
    """A stored snapshot spec stays frozen even when it does not match the live diagram."""
    submission = LearningSubmission(
        assignment_id=1,
        student_user_id=2,
        diagram_id="diag-1",
        status=SUBMISSION_STATUS_SUBMITTED,
        snapshot_spec={"spec": {"unrecognized": True}, "diagram_type": "mind_map", "title": "冻结"},
    )
    live = {
        "title": "草稿",
        "diagram_type": "bubble_map",
        "spec": {"nodes": [{"id": "topic", "text": "中心"}]},
    }
    _thumb, spec, diagram_type, title = _resolve_submission_diagram_fields(submission, live)
    assert spec is None
    assert diagram_type == "mind_map"
    assert title == "冻结"
