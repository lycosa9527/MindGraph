"""Unit tests for Learning Space helpers and AI gate.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from models.domain.learning_space import (
    ASSIGNMENT_STATUS_ACTIVE,
    SUBMISSION_STATUS_DRAFT,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningSubmission,
)
from routers.features.learning_space.schemas import ClassUpdate
from services.diagram.semantic_spec_validation import validate_semantic_spec
from services.learning_space.assignments import (
    assert_can_edit_submission,
    student_homework_diagram_title,
    student_open_diagram_payload,
)
from services.learning_space.admin_teachers import (
    assert_teacher_eligible_for_pilot,
)
from services.learning_space.blank_spec import blank_spec_for_type, resolve_template_role
from services.learning_space.memberships import normalize_account_phone, parse_account_phones
from services.learning_space.passwords import (
    ai_permission_allowed,
    generate_class_code,
    initial_password_from_name,
    merge_ai_permissions,
    normalize_student_name,
)
from services.learning_space.students import preview_student_names
from tests.typing_helpers import as_type, as_user


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


def test_initial_password_from_chinese_name() -> None:
    """Derive the default student password from pinyin initials."""
    assert initial_password_from_name("张三") == "zs123"


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


def test_assert_can_edit_already_submitted() -> None:
    """Block edits once a submission is already submitted."""
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
    with pytest.raises(HTTPException) as exc:
        assert_can_edit_submission(assignment, submission)
    assert "Already submitted" in str(exc.value.detail)


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
    assert spec["analogies"][0]["left"] == "…"
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
