"""Admin activity classification and persistence (no database required)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.admin.activity_catalog import (
    classify_admin_activity,
    feature_access_detail,
    feature_flags_only,
    known_admin_activity_actions,
    public_setting_changes,
    resolve_admin_action,
)
from services.admin.activity_record import note_admin_activity, record_admin_activity


def test_create_school_and_invite_rotation_are_classified() -> None:
    """School create and both invitation-code rotations map to stable actions."""
    assert classify_admin_activity("POST", "/api/auth/admin/organizations") == "organization.create"
    assert (
        classify_admin_activity("POST", "/api/auth/admin/organizations/4/refresh-invitation-code")
        == "organization.invitation_rotate"
    )
    assert (
        classify_admin_activity("POST", "/api/auth/admin/school/invitation-code/rotate") == "school.invitation_rotate"
    )


def test_password_resets_are_classified_without_reading_a_body() -> None:
    """Superadmin and school-manager password resets are distinct actions."""
    assert classify_admin_activity("PUT", "/api/auth/admin/users/9/reset-password") == "user.password_reset"
    assert (
        classify_admin_activity("POST", "/api/learning-space/admin/students/9/reset-password")
        == "learning_space.password_reset"
    )


def test_feature_flag_write_is_promoted() -> None:
    """A settings write that only flips FEATURE_* flags is a feature toggle."""
    detail = {"changes": [{"key": "FEATURE_VOD", "value": "False"}]}
    assert feature_flags_only(detail)
    assert resolve_admin_action("PUT", "/api/auth/admin/env/settings", detail) == "feature.flag_update"


def test_mixed_settings_stay_settings_update() -> None:
    """A settings write that includes a non-feature key stays a settings update."""
    detail = {
        "changes": [
            {"key": "FEATURE_VOD", "value": "True"},
            {"key": "SERVER_URL", "value": "https://example.test"},
        ]
    }
    assert resolve_admin_action("PUT", "/api/auth/admin/env/settings", detail) == "settings.update"


def test_secrets_are_masked() -> None:
    """Passwords, key material, and connection strings are not stored."""
    rows = public_setting_changes(
        {
            "FEATURE_LIBRARY": "True",
            "QWEN_API_KEY": "sk-secret",
            "DB_PASSWORD": "hunter2",
            "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE",
            "REDIS_URL": "redis://:secret@localhost:6379/0",
            "SERVER_URL": "https://example.test",
            "SMTP_PASSWORD": "***...abcd",
        }
    )
    by_key = {row["key"]: row["value"] for row in rows}
    assert by_key["FEATURE_LIBRARY"] == "True"
    assert by_key["QWEN_API_KEY"] == "***"
    assert by_key["DB_PASSWORD"] == "***"
    assert by_key["AWS_ACCESS_KEY_ID"] == "***"
    assert by_key["REDIS_URL"] == "***"
    assert by_key["SERVER_URL"] == "https://example.test"
    assert by_key["SMTP_PASSWORD"] == "***"


def test_settings_tab_lists_every_catalog_action() -> None:
    """The activity filter offers every action the server can record."""
    text = Path("frontend/src/components/admin/AdminActivitiesTab.vue").read_text(encoding="utf-8")
    missing = sorted(action for action in known_admin_activity_actions() if f"'{action}'" not in text)
    assert missing == []


def test_library_catalog_and_device_assign_are_classified() -> None:
    """Admin library writes and device assignment are logged; reader actions are not."""
    assert classify_admin_activity("POST", "/api/library/books/register") == "library.change"
    assert classify_admin_activity("POST", "/api/library/books/register-batch") == "library.change"
    assert classify_admin_activity("PUT", "/api/library/documents/4") == "library.change"
    assert classify_admin_activity("POST", "/api/library/documents/4/cover") == "library.change"
    assert classify_admin_activity("DELETE", "/api/library/documents/4") == "library.change"
    assert classify_admin_activity("PATCH", "/api/library/documents/4/visibility") == "library.change"
    assert classify_admin_activity("POST", "/api/library/documents/4/bookmarks") is None
    assert classify_admin_activity("POST", "/api/devices/watch-1/assign") == "admin.mutate"
    assert classify_admin_activity("DELETE", "/api/devices/watch-1/assign") == "admin.mutate"
    assert classify_admin_activity("POST", "/api/devices/register") is None


def test_feature_access_detail_keeps_int_ids_only() -> None:
    """A bad id does not raise after the access rules have already been saved."""
    entry = SimpleNamespace(restrict=True, organization_ids=[3, "nope", True], user_ids=[9])
    detail = feature_access_detail({"feature_vod": entry})
    assert detail["rules"] == [
        {"key": "feature_vod", "restrict": True, "organization_ids": [3], "user_ids": [9]},
    ]


def test_regular_user_and_read_requests_are_ignored() -> None:
    """Teachers and GET requests are not admin activities."""
    assert classify_admin_activity("GET", "/api/auth/admin/organizations") is None
    assert classify_admin_activity("POST", "/api/diagrams") is None
    assert classify_admin_activity("POST", "/api/learning-space/teacher/assignments") is None
    assert classify_admin_activity("POST", "/api/auth/admin/organizations/3/mindmate-dify-health") is None


def _request(method: str, path: str) -> SimpleNamespace:
    return SimpleNamespace(
        method=method,
        url=SimpleNamespace(path=path),
        query_params={},
        state=SimpleNamespace(),
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )


def _capturing_session() -> tuple[AsyncMock, object]:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    class _Session:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_exc):
            return False

    return session, _Session()


@pytest.mark.asyncio
async def test_school_manager_password_reset_is_stored() -> None:
    """A successful school-manager password reset is written once, without a password."""
    request = _request("POST", "/api/learning-space/admin/students/12/reset-password")
    response = SimpleNamespace(status_code=200)
    user = SimpleNamespace(id=7, role="school_admin", name="Ada", phone="13800000000", organization_id=3)
    session, session_cm = _capturing_session()

    with (
        patch("services.admin.activity_record.system_rls_session", return_value=session_cm),
        patch("services.admin.activity_record.is_env_configured_superadmin", return_value=False),
    ):
        await record_admin_activity(request, response, user)

    session.add.assert_called_once()
    row = session.add.call_args.args[0]
    assert row.action == "learning_space.password_reset"
    assert row.actor_role == "school_admin"
    assert row.actor_label == "Ada"
    assert row.organization_id == 3
    assert row.detail is None
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_teacher_write_is_not_stored() -> None:
    """A teacher using the product does not create an admin activity row."""
    request = _request("POST", "/api/auth/admin/organizations")
    response = SimpleNamespace(status_code=200)
    user = SimpleNamespace(id=8, role="teacher", name="Bo", organization_id=3)
    with patch("services.admin.activity_record.system_rls_session") as session_cm:
        await record_admin_activity(request, response, user)
    session_cm.assert_not_called()


@pytest.mark.asyncio
async def test_feature_toggle_detail_is_stored() -> None:
    """Feature on/off notes the flag and the new value, not unrelated secrets."""
    request = _request("PUT", "/api/auth/admin/env/settings")
    note_admin_activity(
        request,
        {"changes": public_setting_changes({"FEATURE_VOD": "False"})},
    )
    response = SimpleNamespace(status_code=200)
    user = SimpleNamespace(id=1, role="superadmin", name="Root", phone="13900000000", organization_id=None)
    session, session_cm = _capturing_session()

    with (
        patch("services.admin.activity_record.system_rls_session", return_value=session_cm),
        patch("services.admin.activity_record.is_env_configured_superadmin", return_value=False),
    ):
        await record_admin_activity(request, response, user)

    row = session.add.call_args.args[0]
    assert row.action == "feature.flag_update"
    assert row.detail["changes"] == [{"key": "FEATURE_VOD", "value": "False"}]


@pytest.mark.asyncio
async def test_env_superadmin_is_stored_as_superadmin() -> None:
    """An env-configured superadmin is recorded as superadmin even when the DB role differs."""
    request = _request("POST", "/api/auth/admin/organizations")
    response = SimpleNamespace(status_code=200)
    user = SimpleNamespace(id=4, role="teacher", name="Env", phone="13700000000", organization_id=None)
    session, session_cm = _capturing_session()

    with (
        patch("services.admin.activity_record.system_rls_session", return_value=session_cm),
        patch("services.admin.activity_record.is_env_configured_superadmin", return_value=True),
        patch("utils.auth.admin_panel_permissions.is_env_configured_superadmin", return_value=True),
    ):
        await record_admin_activity(request, response, user)

    row = session.add.call_args.args[0]
    assert row.actor_role == "superadmin"
    assert row.action == "organization.create"
    session.commit.assert_awaited()
