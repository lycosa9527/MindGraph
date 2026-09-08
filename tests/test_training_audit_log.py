"""Training / Course Builder operator audit logs."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from models.domain.auth import User
from routers.api.training_course_routes import CourseWriteBody, create_training_course
from routers.api.training_play_routes import play_course
from routers.api.training_routes import create_session, org_ready
from services.features.training.courses.constants import DOUBLE_BUBBLE_COURSE_ID
from services.features.training.payloads import PlayBody, StartSessionBody
from services.features.training.storage import backend as storage_backend
from services.features.training.storage.backend import delete_course_prefix, put_bytes_sync
from services.features.training.training_logger import (
    bilingual_label,
    format_training_line,
    log_training,
    step_type_summary,
    training_extra,
)


def _user(role: str, *, user_id: int = 1, org_id: int | None = 10) -> User:
    return cast(User, SimpleNamespace(id=user_id, role=role, organization_id=org_id, name=role))


def _rls(db: AsyncMock) -> AsyncMock:
    context = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


def _course() -> SimpleNamespace:
    return SimpleNamespace(
        id=DOUBLE_BUBBLE_COURSE_ID,
        title={"zh": "未命名课程", "en": "Untitled course"},
        description={"zh": "", "en": ""},
        status="draft",
        is_system=False,
        cover_asset_id=None,
        assets=[],
        steps=[],
        updated_at=None,
    )


def test_bilingual_label_prefers_zh() -> None:
    """Course titles in logs use the Chinese field when present."""
    assert bilingual_label({"zh": "校本课", "en": "School course"}) == "校本课"
    assert bilingual_label({"en": "Only English"}) == "Only English"
    assert bilingual_label(None) == ""


def test_step_type_summary_counts_and_unchanged() -> None:
    """Saves log a compact inventory, or unchanged when steps were omitted."""
    assert step_type_summary(None) == "unchanged"
    assert step_type_summary([]) == "0"
    assert step_type_summary([{"type": "slide"}, {"step_type": "canvas"}, {"type": "slide"}]) == "3(canvas:1,slide:2)"


def test_format_training_line_skips_empty_and_formats_bools() -> None:
    """Operator lines stay greppable and omit blank scope fields."""
    line = format_training_line(
        "course_play",
        org_id=10,
        course_id="",
        pull_users=True,
        teachers=12,
    )
    assert line == "[Training] course_play org_id=10 pull_users=true teachers=12"


def test_log_training_sets_structured_extra(caplog: pytest.LogCaptureFixture) -> None:
    """JSON backends can index tr_event without parsing the message."""
    probe = logging.getLogger("tests.training_audit")
    with caplog.at_level(logging.INFO, logger=probe.name):
        log_training(
            probe,
            "course_created",
            actor_id=7,
            course_id="abc",
            title="校本课",
        )
    record = next(item for item in caplog.records if "course_created" in item.message)
    assert getattr(record, "tr_event") == "course_created"
    assert getattr(record, "tr_actor_id") == 7
    assert getattr(record, "tr_course_id") == "abc"
    assert getattr(record, "tr_title") == "校本课"
    extra = training_extra(event="x", teacher_total=4)
    assert extra["tr_event"] == "x"
    assert extra["tr_teacher_total"] == 4


@pytest.mark.asyncio
async def test_create_course_logs_title_and_owner(caplog: pytest.LogCaptureFixture) -> None:
    """Creating a draft records what was created and who owns it."""
    course = _course()
    db = AsyncMock()
    with (
        caplog.at_level(logging.INFO, logger="routers.api.training_course_routes"),
        patch("routers.api.training_course_routes.can_lead_any_training", return_value=True),
        patch("routers.api.training_course_routes.system_rls_session", return_value=_rls(db)),
        patch("routers.api.training_course_routes.create_course", new=AsyncMock(return_value=course)),
        patch("routers.api.training_course_routes.save_course", new=AsyncMock(return_value=course)),
        patch("routers.api.training_course_routes.get_course", new=AsyncMock(return_value=course)),
    ):
        body = await create_training_course(
            CourseWriteBody(title={"zh": "未命名课程", "en": "Untitled course"}),
            current_user=_user("superadmin"),
        )
    assert body["id"] == DOUBLE_BUBBLE_COURSE_ID
    text = caplog.text
    assert "course_created" in text
    assert DOUBLE_BUBBLE_COURSE_ID in text
    assert "未命名课程" in text
    assert "owner_id=1" in text


@pytest.mark.asyncio
async def test_org_ready_logs_teacher_counts(caplog: pytest.LogCaptureFixture) -> None:
    """Ready confirm logs how many teachers the org has and who is online."""
    db = AsyncMock()
    with (
        caplog.at_level(logging.INFO, logger="routers.api.training_routes"),
        patch("routers.api.training_routes.can_lead_training", new=AsyncMock(return_value=True)),
        patch("routers.api.training_routes.system_rls_session", return_value=_rls(db)),
        patch("routers.api.training_routes.count_org_teachers", new=AsyncMock(return_value=18)),
        patch(
            "routers.api.training_routes.activity_summary",
            new=AsyncMock(return_value={"online": 5, "generating": 2, "done": 1}),
        ),
    ):
        body = await org_ready(10, current_user=_user("superadmin"))
    assert body["teacher_total"] == 18
    assert body["online_now"] == 5
    assert "org_ready" in caplog.text
    assert "teachers=18" in caplog.text
    assert "online=5" in caplog.text


@pytest.mark.asyncio
async def test_start_confirm_mismatch_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Stale confirm totals are visible in the log before the 409."""
    db = AsyncMock()
    with (
        caplog.at_level(logging.WARNING, logger="routers.api.training_routes"),
        patch("routers.api.training_routes.can_lead_training", new=AsyncMock(return_value=True)),
        patch("routers.api.training_routes.system_rls_session", return_value=_rls(db)),
        patch("routers.api.training_routes.count_org_teachers", new=AsyncMock(return_value=9)),
    ):
        with pytest.raises(HTTPException) as exc:
            await create_session(
                StartSessionBody(org_id=10, confirm_teacher_total=5),
                current_user=_user("superadmin", org_id=None),
            )
    assert exc.value.status_code == 409
    assert "session_confirm_mismatch" in caplog.text
    assert "teachers=9" in caplog.text
    assert "confirm=5" in caplog.text


@pytest.mark.asyncio
async def test_play_logs_pull_and_teacher_counts(caplog: pytest.LogCaptureFixture) -> None:
    """Playing a course logs the pull and how many teachers are in the room."""
    session = {
        "session_id": "sess-1",
        "org_id": 10,
        "instructor_id": 1,
        "state": "live",
        "seq": 2,
        "confirm_teacher_count": 18,
        "pull_users": False,
    }
    updated = {
        **session,
        "seq": 3,
        "course_id": DOUBLE_BUBBLE_COURSE_ID,
        "pull_users": True,
        "step_index": 0,
    }
    steps = [{"type": "canvas", "page_key": "canvas", "diagram_type": "double_bubble_map"}]
    with (
        caplog.at_level(logging.INFO, logger="routers.api.training_play_routes"),
        patch("routers.api.training_play_routes.can_lead_training", new=AsyncMock(return_value=True)),
        patch("routers.api.training_play_routes.require_owner_active", new=AsyncMock(return_value=session)),
        patch("routers.api.training_play_routes._load_serialized_steps", new=AsyncMock(return_value=steps)),
        patch("routers.api.training_play_routes.bump_and_save", new=AsyncMock(return_value=updated)),
        patch("routers.api.training_play_routes.publish_event", new=AsyncMock()),
        patch(
            "routers.api.training_play_routes.activity_summary",
            new=AsyncMock(return_value={"online": 6, "generating": 1, "done": 0}),
        ),
    ):
        body = await play_course(
            "sess-1",
            PlayBody(course_id=DOUBLE_BUBBLE_COURSE_ID),
            org_id=10,
            current_user=_user("superadmin"),
        )
    assert body["seq"] == 3
    text = caplog.text
    assert "course_play" in text
    assert "teachers=18" in text
    assert "online=6" in text
    assert "pull_users=true" in text
    assert "steps=1" in text


def test_put_bytes_logs_local_write(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Local fallback still records what was written."""
    monkeypatch.setattr(storage_backend, "cos_training_enabled", lambda: False)
    monkeypatch.chdir(tmp_path)
    key = f"courses/{DOUBLE_BUBBLE_COURSE_ID}/cover.png"
    with caplog.at_level(logging.INFO, logger="services.features.training.storage.backend"):
        put_bytes_sync(key, b"png-bytes", content_type="image/png")
    assert "put_bytes" in caplog.text
    assert "backend=local" in caplog.text
    assert key in caplog.text
    assert "bytes=9" in caplog.text
    assert "uploaded=true" in caplog.text


def test_delete_course_folder_logs_local_removal(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Course delete logs whether the local folder was removed."""
    monkeypatch.setattr(storage_backend, "cos_training_enabled", lambda: False)
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "static" / "training" / "courses" / DOUBLE_BUBBLE_COURSE_ID
    folder.mkdir(parents=True)
    (folder / "cover.png").write_bytes(b"png")
    with caplog.at_level(logging.INFO, logger="services.features.training.storage.backend"):
        delete_course_prefix(DOUBLE_BUBBLE_COURSE_ID)
    assert "delete_course_folder" in caplog.text
    assert f"course_id={DOUBLE_BUBBLE_COURSE_ID}" in caplog.text
    assert "local_removed=true" in caplog.text
    assert "cos_deleted=0" in caplog.text
