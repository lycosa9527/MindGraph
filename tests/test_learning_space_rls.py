"""Learning Space RLS is school-scoped and must not use the any-login shortcut."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

import config.database as _database_bootstrap
from utils.db.rls_context import RlsContext, rls_async_session

assert _database_bootstrap.AsyncSessionLocal is not None
from utils.db_rls.policy_builder import (
    LEARNING_ASSIGNMENT_EXPR,
    LEARNING_CLASS_EXPR,
    LEARNING_MEMBERSHIP_EXPR,
    LEARNING_PILOT_EXPR,
    LEARNING_SPACE_POLICIES,
    LEARNING_SUBMISSION_EXPR,
)

pytestmark_rls_db = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)

_LOOSE = "rls_current_user_id() IS NOT NULL"
_REV_0125 = Path("alembic/versions/rev_0125_learning_space_school_rls.py")


def test_learning_space_policies_are_school_scoped() -> None:
    """Every Learning Space table uses org visibility, not any authenticated user."""
    assert len(LEARNING_SPACE_POLICIES) == 5
    for table, expr in LEARNING_SPACE_POLICIES:
        assert "rls_org_id_in_readable_list(organization_id)" in expr, table
        assert "rls_panel_legacy_org_visible" not in expr, table
        assert _LOOSE not in expr, table
        assert "rls_is_system_mode()" in expr, table


def test_out_of_org_participants_are_not_blocked() -> None:
    """Imported learners/assistants still match via membership or classroom student."""
    assert "learning_class_memberships" in LEARNING_CLASS_EXPR
    assert "u.learning_class_id = learning_classes.id" in LEARNING_CLASS_EXPR
    assert "u.learning_class_id = learning_assignments.class_id" in LEARNING_ASSIGNMENT_EXPR
    assert "learning_class_memberships" in LEARNING_ASSIGNMENT_EXPR
    assert "student_user_id = rls_current_user_id()" in LEARNING_SUBMISSION_EXPR
    assert "user_id = rls_current_user_id()" in LEARNING_MEMBERSHIP_EXPR
    assert "teacher_user_id = rls_current_user_id()" in LEARNING_PILOT_EXPR
    assert "teacher_user_id = rls_current_user_id()" in LEARNING_CLASS_EXPR


def test_panel_mode_alone_is_not_enough() -> None:
    """Panel access is org-scoped; the legacy all-uninvited-orgs path is excluded."""
    for _table, expr in LEARNING_SPACE_POLICIES:
        assert "rls_panel_global_read()" in expr
        assert "rls_panel_legacy_org_visible" not in expr


def test_student_login_uses_system_rls_for_class_code() -> None:
    """Class-code login must run in system mode so school RLS does not hide the class."""
    login_src = Path("routers/auth/login.py").read_text(encoding="utf-8")
    assert "login/student" in login_src
    assert "bind_system_bootstrap_rls_dependency" in login_src


def test_migration_0125_replaces_loose_policies() -> None:
    """0125 drops the 0121/0124 any-login policies."""
    source = _REV_0125.read_text(encoding="utf-8")
    assert "upgrade_learning_space_policies" in source
    assert "organization_id" in source
    assert "0124" in source


@pytest.mark.asyncio
@pytestmark_rls_db
async def test_two_schools_cannot_see_each_others_learning_space() -> None:
    """Seed two schools and assert RLS hides the other school's class and homework."""
    code_a = "ZZLS1A"
    code_b = "ZZLS1B"
    codes_sql = "SELECT class_code FROM learning_classes WHERE class_code IN (:a, :b)"
    homework_sql = "SELECT title FROM learning_assignments WHERE class_id IN (:ca, :cb)"
    async with rls_async_session(RlsContext(mode="system")) as session:
        await session.execute(
            text("DELETE FROM learning_classes WHERE class_code IN (:a, :b)"),
            {"a": code_a, "b": code_b},
        )
        row_a = (
            await session.execute(text("SELECT id FROM users WHERE organization_id = 1 ORDER BY id LIMIT 1"))
        ).first()
        row_b = (
            await session.execute(
                text(
                    "SELECT id, organization_id FROM users "
                    "WHERE organization_id IS NOT NULL AND organization_id <> 1 "
                    "ORDER BY id LIMIT 1"
                )
            )
        ).first()
        if row_a is None or row_b is None:
            pytest.skip("need users in two organizations")
        teacher_a = int(row_a[0])
        teacher_b = int(row_b[0])
        org_b = int(row_b[1])
        await session.execute(
            text(
                """
                INSERT INTO learning_classes (
                    name, class_code, teacher_user_id, organization_id, status, max_students
                ) VALUES
                    ('LS RLS A', :ca, :ta, 1, 'active', 60),
                    ('LS RLS B', :cb, :tb, :ob, 'active', 60)
                """
            ),
            {"ca": code_a, "cb": code_b, "ta": teacher_a, "tb": teacher_b, "ob": org_b},
        )
        ids = (
            await session.execute(
                text("SELECT id, organization_id, class_code FROM learning_classes WHERE class_code IN (:a, :b)"),
                {"a": code_a, "b": code_b},
            )
        ).all()
        await session.commit()
    class_by_code = {row[2]: (int(row[0]), int(row[1])) for row in ids}
    class_a_id, org_a = class_by_code[code_a]
    class_b_id, org_b = class_by_code[code_b]
    assert org_a != org_b

    async with rls_async_session(RlsContext(mode="system")) as session:
        await session.execute(
            text(
                """
                INSERT INTO learning_assignments (
                    class_id, title, instructions, template_diagram_id,
                    organization_id, created_by, status
                ) VALUES
                    (:cid, 'Homework A', '', 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', :oa, :ta, 'active')
                """
            ),
            {"cid": class_a_id, "oa": org_a, "ta": teacher_a},
        )
        await session.commit()

    ctx_a = RlsContext(mode="authenticated", user_id=teacher_a, organization_id=org_a)
    ctx_b = RlsContext(mode="authenticated", user_id=teacher_b, organization_id=org_b)
    try:
        async with rls_async_session(ctx_a) as session:
            seen = (await session.execute(text(codes_sql), {"a": code_a, "b": code_b})).scalars().all()
            homework = (
                (
                    await session.execute(
                        text(homework_sql),
                        {"ca": class_a_id, "cb": class_b_id},
                    )
                )
                .scalars()
                .all()
            )
        assert seen == [code_a]
        assert homework == ["Homework A"]

        async with rls_async_session(ctx_b) as session:
            seen_b = (await session.execute(text(codes_sql), {"a": code_a, "b": code_b})).scalars().all()
            homework_b = (
                (
                    await session.execute(
                        text(homework_sql),
                        {"ca": class_a_id, "cb": class_b_id},
                    )
                )
                .scalars()
                .all()
            )
        assert seen_b == [code_b]
        assert homework_b == []

        guest_ids: tuple[int, int] | None = None
        async with rls_async_session(RlsContext(mode="system")) as session:
            guest = (
                await session.execute(
                    text(
                        "SELECT id, organization_id FROM users "
                        "WHERE organization_id IS NOT NULL "
                        "AND organization_id NOT IN (:oa, :ob) "
                        "AND id NOT IN (:ta, :tb) "
                        "ORDER BY id LIMIT 1"
                    ),
                    {"oa": org_a, "ob": org_b, "ta": teacher_a, "tb": teacher_b},
                )
            ).first()
            if guest is not None:
                await session.execute(
                    text(
                        """
                        INSERT INTO learning_class_memberships (
                            class_id, user_id, organization_id, role
                        ) VALUES (:cid, :uid, :oa, 'learner')
                        """
                    ),
                    {"cid": class_a_id, "uid": int(guest[0]), "oa": org_a},
                )
                await session.commit()
                guest_ids = (int(guest[0]), int(guest[1]))
        if guest_ids is not None:
            guest_ctx = RlsContext(
                mode="authenticated",
                user_id=guest_ids[0],
                organization_id=guest_ids[1],
            )
            async with rls_async_session(guest_ctx) as guest_session:
                guest_seen = (await guest_session.execute(text(codes_sql), {"a": code_a, "b": code_b})).scalars().all()
            assert guest_seen == [code_a]

        async with rls_async_session(RlsContext.deny_default()) as session:
            locked = (
                await session.execute(
                    text("SELECT count(*) FROM learning_classes WHERE class_code IN (:a, :b)"),
                    {"a": code_a, "b": code_b},
                )
            ).scalar_one()
        assert int(locked) == 0

        panel_b = RlsContext(
            mode="panel",
            user_id=teacher_b,
            organization_id=org_b,
            role="school_admin",
            readable_org_ids=str(org_b),
            panel_global_read=False,
        )
        async with rls_async_session(panel_b) as session:
            panel_seen = (await session.execute(text(codes_sql), {"a": code_a, "b": code_b})).scalars().all()
        assert panel_seen == [code_b]
    finally:
        async with rls_async_session(RlsContext(mode="system")) as session:
            await session.execute(
                text("DELETE FROM learning_classes WHERE class_code IN (:a, :b)"),
                {"a": code_a, "b": code_b},
            )
            await session.commit()
