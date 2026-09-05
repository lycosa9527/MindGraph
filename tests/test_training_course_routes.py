"""Course builder REST: teachers cannot author; seed is listed."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from models.domain.auth import User
from models.domain.training import TrainingCourseAsset
from routers.api.training_asset_routes import (
    AssetInitBody,
    can_read_training_asset,
    complete_training_asset,
    init_training_asset,
)
from routers.api.training_course_routes import (
    CourseWriteBody,
    list_training_courses,
    remove_training_course,
    update_training_course,
)
from routers.api.training_play_routes import play_course
from services.features.training.courses.constants import (
    DOUBLE_BUBBLE_COURSE_ID,
    FOCUS_KEYS,
    MODAL_KEYS,
    STEP_TYPES,
    clamped_mark_step,
    optional_notes,
    optional_step_key,
)
from services.features.training.courses.cover_png import build_double_bubble_cover_png
from services.features.training.courses.seed import ensure_double_bubble_seed
from services.features.training.courses.serialize import (
    localized_text,
    snapshot_step_payload,
    step_navigation_fields,
    step_preview_url,
)
from services.features.training.payloads import PlayBody, snapshot_from_session
from services.features.training.storage.keys import course_id_from_key


def _user(role: str, *, user_id: int = 2, org_id: int | None = 10) -> User:
    """Build a lightweight user stand-in."""
    return cast(User, SimpleNamespace(id=user_id, role=role, organization_id=org_id, name=role))


def _rls(db: AsyncMock) -> AsyncMock:
    """Async context manager that yields the given session mock."""
    context = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


@pytest.mark.asyncio
async def test_teacher_cannot_list_courses() -> None:
    """Teachers are blocked from the course catalog."""
    with pytest.raises(HTTPException) as exc:
        await list_training_courses(locale="zh", current_user=_user("teacher"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_init_upload_accepts_filename_without_suffix() -> None:
    """Browser camera/blob files often have no extension."""
    course = SimpleNamespace(id=DOUBLE_BUBBLE_COURSE_ID)
    db = AsyncMock()
    with (
        patch("routers.api.training_asset_routes.can_lead_any_training", return_value=True),
        patch("routers.api.training_asset_routes.system_rls_session", return_value=_rls(db)),
        patch(
            "routers.api.training_asset_routes.get_course",
            new=AsyncMock(return_value=course),
        ),
        patch("routers.api.training_asset_routes.save_upload_grant", new=AsyncMock()),
        patch("routers.api.training_asset_routes.create_presigned_put", return_value=None),
    ):
        body = await init_training_asset(
            AssetInitBody(
                course_id=DOUBLE_BUBBLE_COURSE_ID,
                role="slide",
                filename="blob",
                content_type="image/png",
                size_bytes=12,
            ),
            current_user=_user("superadmin", user_id=1),
        )
    assert body["key"].endswith(".png")
    assert "/slides/" in body["key"]


@pytest.mark.asyncio
async def test_complete_upload_stores_bytes_and_returns_url() -> None:
    """Complete writes the file through the API and binds it to the course."""
    logical_key = f"courses/{DOUBLE_BUBBLE_COURSE_ID}/slides/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee.png"
    upload = UploadFile(
        filename="slide.png",
        file=BytesIO(b"\x89PNG\r\n\x1a\n"),
        headers=Headers({"content-type": "image/png"}),
    )
    asset = SimpleNamespace(id="asset-1", role="slide", logical_key=logical_key)
    course = SimpleNamespace(id=DOUBLE_BUBBLE_COURSE_ID)
    db = AsyncMock()
    with (
        patch("routers.api.training_asset_routes.can_lead_any_training", return_value=True),
        patch(
            "routers.api.training_asset_routes.pop_upload_grant",
            new=AsyncMock(
                return_value={
                    "key": logical_key,
                    "course_id": DOUBLE_BUBBLE_COURSE_ID,
                    "content_type": "image/png",
                    "max_bytes": 20 * 1024 * 1024,
                    "role": "slide",
                }
            ),
        ),
        patch("routers.api.training_asset_routes.put_bytes", new=AsyncMock()) as put,
        patch("routers.api.training_asset_routes.system_rls_session", return_value=_rls(db)),
        patch(
            "routers.api.training_asset_routes.get_course",
            new=AsyncMock(return_value=course),
        ),
        patch("routers.api.training_asset_routes.add_asset", new=AsyncMock(return_value=asset)),
    ):
        body = await complete_training_asset(
            course_id=DOUBLE_BUBBLE_COURSE_ID,
            role="slide",
            key=logical_key,
            asset_id="asset-1",
            file=upload,
            current_user=_user("superadmin", user_id=1),
        )
    put.assert_awaited()
    assert body["id"] == "asset-1"
    assert body["url"] == f"/api/training/assets/{logical_key}"


@pytest.mark.asyncio
async def test_teacher_cannot_init_upload() -> None:
    """Teachers cannot start a COS upload grant."""
    with pytest.raises(HTTPException) as exc:
        await init_training_asset(
            AssetInitBody(
                course_id=DOUBLE_BUBBLE_COURSE_ID,
                role="cover",
                filename="cover.png",
                content_type="image/png",
                size_bytes=12,
            ),
            current_user=_user("teacher"),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_leader_lists_seeded_double_bubble() -> None:
    """Instructors see the seeded 双气泡图 course from the API."""
    course = SimpleNamespace(
        id=DOUBLE_BUBBLE_COURSE_ID,
        title={"zh": "双气泡图教程", "en": "Double Bubble Map tutorial"},
        description={"zh": "对比辨析两个对象。", "en": "Compare and contrast two topics."},
        status="ready",
        is_system=True,
        cover_asset_id=None,
        assets=[],
        steps=[
            SimpleNamespace(
                id="s1",
                position=0,
                step_type="canvas",
                payload={"diagram_type": "double_bubble_map", "topic_options": []},
            )
        ],
        updated_at=None,
    )
    db = AsyncMock()
    with (
        patch("routers.api.training_course_routes.can_lead_any_training", return_value=True),
        patch("routers.api.training_course_routes.system_rls_session", return_value=_rls(db)),
        patch(
            "routers.api.training_course_routes.ensure_double_bubble_seed",
            new=AsyncMock(),
        ),
        patch("routers.api.training_course_routes.list_courses", new=AsyncMock(return_value=[course])),
    ):
        body = await list_training_courses(locale="zh", current_user=_user("superadmin", user_id=1))
    assert body["items"][0]["id"] == DOUBLE_BUBBLE_COURSE_ID
    assert "双气泡" in body["items"][0]["title"]


@pytest.mark.asyncio
async def test_play_bumps_seq_and_binds_course() -> None:
    """Play binds the course and increments seq."""
    session = {
        "session_id": "sess-1",
        "org_id": 10,
        "instructor_id": 1,
        "state": "live",
        "seq": 2,
        "course_id": None,
        "step_index": 0,
        "step": None,
    }
    updated = {**session, "seq": 3, "course_id": DOUBLE_BUBBLE_COURSE_ID}
    steps = [
        {
            "type": "canvas",
            "diagram_type": "double_bubble_map",
            "topic_options": [{"id": "ice-water", "label": "ice vs water"}],
            "asset_url": None,
            "overlays": [],
        }
    ]
    with (
        patch("routers.api.training_play_routes.can_lead_training", new=AsyncMock(return_value=True)),
        patch("routers.api.training_play_routes.require_owner_active", new=AsyncMock(return_value=session)),
        patch("routers.api.training_play_routes._load_serialized_steps", new=AsyncMock(return_value=steps)),
        patch("routers.api.training_play_routes.bump_and_save", new=AsyncMock(return_value=updated)) as bump,
        patch("routers.api.training_play_routes.publish_event", new=AsyncMock()),
    ):
        body = await play_course(
            "sess-1",
            PlayBody(course_id=DOUBLE_BUBBLE_COURSE_ID),
            org_id=10,
            current_user=_user("superadmin", user_id=1),
        )
    assert body["seq"] == 3
    assert body["course_id"] == DOUBLE_BUBBLE_COURSE_ID
    bump.assert_awaited()


def test_snapshot_includes_course_fields() -> None:
    """Command snapshot exposes course_id and step."""
    empty = snapshot_from_session(None)
    assert empty["course_id"] is None
    assert empty["step"] is None
    filled = snapshot_from_session(
        {
            "state": "live",
            "session_id": "s",
            "org_id": 1,
            "seq": 2,
            "course_id": DOUBLE_BUBBLE_COURSE_ID,
            "step_index": 0,
            "step": {"type": "canvas"},
        }
    )
    assert filled["course_id"] == DOUBLE_BUBBLE_COURSE_ID
    assert filled["step"]["type"] == "canvas"


def test_snapshot_hides_notes_from_teachers() -> None:
    """Speaker notes stay on the instructor command payload only."""
    session = {
        "state": "live",
        "session_id": "s",
        "org_id": 1,
        "seq": 2,
        "instructor_id": 9,
        "course_id": DOUBLE_BUBBLE_COURSE_ID,
        "step_index": 0,
        "step": {"type": "page", "notes": "先点注册"},
    }
    teacher = snapshot_from_session(session, viewer_user_id=3)
    instructor = snapshot_from_session(session, viewer_user_id=9)
    assert "notes" not in teacher["step"]
    assert instructor["step"]["notes"] == "先点注册"


def test_localized_text_and_cover_png() -> None:
    """Bilingual fields and the seed cover PNG are well-formed."""
    assert localized_text({"zh": "甲", "en": "A"}, "zh") == "甲"
    assert localized_text({"zh": "甲", "en": "A"}, "en") == "A"
    png = build_double_bubble_cover_png()
    assert png.startswith(b"\x89PNG")
    step = snapshot_step_payload(
        {
            "type": "page",
            "page_key": "mindgraph",
            "pull_users": True,
            "asset_url": "/api/training/assets/courses/x/slides/a.png",
            "overlays": [],
            "modal_key": "language-settings",
            "focus_key": "mindmap-v2",
            "notes": "点击思维导图",
        }
    )
    assert step["asset_url"].startswith("/api/training/assets/")
    assert step["page_key"] == "mindgraph"
    assert step["pull_users"] is True
    assert step["modal_key"] == "language-settings"
    assert step["focus_key"] == "mindmap-v2"
    assert step["notes"] == "点击思维导图"
    assert step["mark_step"] == 1
    assert step["mark_steps"] == 1
    assert clamped_mark_step(3) == 3
    assert clamped_mark_step(0) == 1
    assert clamped_mark_step(99) == 8


def test_page_step_type_is_allowed() -> None:
    """Auth and other app pages persist as step type page."""
    assert "page" in STEP_TYPES


def test_optional_step_key_allowlist() -> None:
    """Page follow targets accept only the closed modal/button catalog."""
    assert optional_step_key("", MODAL_KEYS, "modal_key") is None
    assert optional_step_key("language-settings", MODAL_KEYS, "modal_key") == "language-settings"
    assert optional_step_key("diagram-mindmap", FOCUS_KEYS, "focus_key") == "diagram-mindmap"
    assert optional_step_key("auth-register", FOCUS_KEYS, "focus_key") == "auth-register"
    with pytest.raises(ValueError, match="modal_key"):
        optional_step_key("not-a-modal", MODAL_KEYS, "modal_key")
    with pytest.raises(ValueError, match="focus_key"):
        optional_step_key("window.alert", FOCUS_KEYS, "focus_key")
    assert optional_notes("  讲到这里  ") == "讲到这里"
    with pytest.raises(ValueError, match="notes"):
        optional_notes("x" * 4001)


def test_slide_preview_falls_back_to_the_uploaded_file() -> None:
    """PPT slides use the uploaded file as the filmstrip preview."""
    slide = TrainingCourseAsset(
        id="slide-preview",
        course_id=DOUBLE_BUBBLE_COURSE_ID,
        role="slide",
        logical_key=f"courses/{DOUBLE_BUBBLE_COURSE_ID}/slides/a.png",
        mime="image/png",
        bytes_size=1,
    )
    assert step_preview_url("slide", slide, None) == (
        f"/api/training/assets/courses/{DOUBLE_BUBBLE_COURSE_ID}/slides/a.png"
    )
    thumb = TrainingCourseAsset(
        id="thumb-preview",
        course_id=DOUBLE_BUBBLE_COURSE_ID,
        role="thumb",
        logical_key=f"courses/{DOUBLE_BUBBLE_COURSE_ID}/thumbs/b.png",
        mime="image/png",
        bytes_size=1,
    )
    assert step_preview_url("page", None, thumb) == (
        f"/api/training/assets/courses/{DOUBLE_BUBBLE_COURSE_ID}/thumbs/b.png"
    )


def test_serialize_step_defaults_canvas_pull() -> None:
    """Legacy canvas steps pull teachers to the canvas page."""
    page_key, pull_users = step_navigation_fields("canvas", {"diagram_type": "double_bubble_map", "topic_options": []})
    assert page_key == "canvas"
    assert pull_users is True


def test_grant_cannot_target_another_folder() -> None:
    """A key from another course UUID does not belong to the seed course."""
    other = "11111111-1111-4111-8111-111111111111"
    key = f"courses/{other}/cover.png"
    assert course_id_from_key(key) != DOUBLE_BUBBLE_COURSE_ID


@pytest.mark.asyncio
async def test_system_course_can_be_updated() -> None:
    """Seeded 双气泡图教程 is editable by visiting staff."""
    course = SimpleNamespace(
        id=DOUBLE_BUBBLE_COURSE_ID,
        title={"zh": "双气泡图教程", "en": "Double Bubble Map tutorial"},
        description={"zh": "对比辨析两个对象。", "en": "Compare and contrast two topics."},
        status="ready",
        is_system=True,
        cover_asset_id=None,
        assets=[],
        steps=[],
        updated_at=None,
    )
    db = AsyncMock()
    with (
        patch("routers.api.training_course_routes.can_lead_any_training", return_value=True),
        patch("routers.api.training_course_routes.system_rls_session", return_value=_rls(db)),
        patch(
            "routers.api.training_course_routes.get_course",
            new=AsyncMock(return_value=course),
        ),
        patch("routers.api.training_course_routes.save_course", new=AsyncMock(return_value=course)) as save,
    ):
        body = await update_training_course(
            DOUBLE_BUBBLE_COURSE_ID,
            CourseWriteBody(title={"zh": "改种子课", "en": "Rewrite seed"}),
            current_user=_user("superadmin", user_id=1),
        )
    save.assert_awaited()
    assert body["id"] == DOUBLE_BUBBLE_COURSE_ID
    assert body["is_system"] is True


@pytest.mark.asyncio
async def test_system_course_cannot_be_deleted() -> None:
    """Seeded courses stay read-only on DELETE."""
    course = SimpleNamespace(id=DOUBLE_BUBBLE_COURSE_ID, is_system=True)
    db = AsyncMock()
    with (
        patch("routers.api.training_course_routes.can_lead_any_training", return_value=True),
        patch("routers.api.training_course_routes.system_rls_session", return_value=_rls(db)),
        patch(
            "routers.api.training_course_routes.get_course",
            new=AsyncMock(return_value=course),
        ),
        patch("routers.api.training_course_routes.delete_course", new=AsyncMock()) as delete,
    ):
        with pytest.raises(HTTPException) as exc:
            await remove_training_course(
                DOUBLE_BUBBLE_COURSE_ID,
                current_user=_user("superadmin", user_id=1),
            )
    assert exc.value.status_code == 403
    assert "deleted" in str(exc.value.detail)
    delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_keeps_existing_author_edits() -> None:
    """Re-running the seed must not reset title, steps, or cover."""
    existing = SimpleNamespace(
        id=DOUBLE_BUBBLE_COURSE_ID,
        title={"zh": "已改标题", "en": "Edited title"},
        description={"zh": "已改说明", "en": "Edited desc"},
        status="ready",
        is_system=False,
        steps=[SimpleNamespace(id="edited-step")],
        assets=[SimpleNamespace(id="edited-cover", role="cover")],
        cover_asset_id="edited-cover",
    )
    result = SimpleNamespace(scalar_one_or_none=lambda: existing)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    with patch("services.features.training.courses.seed.put_bytes", new=AsyncMock()) as put:
        course = await ensure_double_bubble_seed(db)
    assert course.title == {"zh": "已改标题", "en": "Edited title"}
    assert course.description == {"zh": "已改说明", "en": "Edited desc"}
    assert course.is_system is True
    assert course.steps == existing.steps
    put.assert_not_awaited()


@pytest.mark.asyncio
async def test_teacher_cannot_read_asset_without_live_session() -> None:
    """Teachers need a live or paused session bound to that course."""
    with (
        patch("routers.api.training_asset_routes.can_lead_any_training", return_value=False),
        patch("routers.api.training_asset_routes.is_org_teacher_target", return_value=True),
        patch("routers.api.training_asset_routes.get_session", new=AsyncMock(return_value=None)),
    ):
        allowed = await can_read_training_asset(_user("teacher"), DOUBLE_BUBBLE_COURSE_ID)
    assert allowed is False


@pytest.mark.asyncio
async def test_teacher_cannot_read_asset_for_other_course() -> None:
    """A live session for course A does not unlock course B assets."""
    session = {"state": "live", "course_id": "11111111-1111-4111-8111-111111111111"}
    with (
        patch("routers.api.training_asset_routes.can_lead_any_training", return_value=False),
        patch("routers.api.training_asset_routes.is_org_teacher_target", return_value=True),
        patch("routers.api.training_asset_routes.get_session", new=AsyncMock(return_value=session)),
    ):
        allowed = await can_read_training_asset(_user("teacher"), DOUBLE_BUBBLE_COURSE_ID)
    assert allowed is False


@pytest.mark.asyncio
async def test_teacher_cannot_read_asset_when_session_ended() -> None:
    """Ended sessions stop asset reads for teachers."""
    session = {"state": "ended", "course_id": DOUBLE_BUBBLE_COURSE_ID}
    with (
        patch("routers.api.training_asset_routes.can_lead_any_training", return_value=False),
        patch("routers.api.training_asset_routes.is_org_teacher_target", return_value=True),
        patch("routers.api.training_asset_routes.get_session", new=AsyncMock(return_value=session)),
    ):
        allowed = await can_read_training_asset(_user("teacher"), DOUBLE_BUBBLE_COURSE_ID)
    assert allowed is False


@pytest.mark.asyncio
async def test_teacher_can_read_asset_for_live_course() -> None:
    """Teachers in the org may read assets for the playing course."""
    session = {"state": "live", "course_id": DOUBLE_BUBBLE_COURSE_ID}
    with (
        patch("routers.api.training_asset_routes.can_lead_any_training", return_value=False),
        patch("routers.api.training_asset_routes.is_org_teacher_target", return_value=True),
        patch("routers.api.training_asset_routes.get_session", new=AsyncMock(return_value=session)),
    ):
        allowed = await can_read_training_asset(_user("teacher"), DOUBLE_BUBBLE_COURSE_ID)
    assert allowed is True
