"""Admin scan stores missing Learning Space card thumbnails on COS."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from models.domain.learning_space import LearningAssignment, LearningSubmission
from routers.api.vueflow_screenshot import DiagramScreenshotError
from services.learning_space.image_storage import IMAGE_REF_PREFIX
from services.learning_space.thumbnail_backfill import (
    fill_missing_card_thumbnails,
    store_rendered_thumbnail,
)
from services.learning_space.thumbnail_backfill_scan import (
    SUBMISSION_THUMBNAIL_OPEN,
    SUBMIT_THUMBNAIL_DUE_SQL,
)
from services.learning_space.thumbnail_storage import stored_submit_thumbnail
from services.learning_space.thumbnail_submit import (
    THUMB_ATTEMPTS,
    THUMB_PENDING,
    THUMB_RETRY_AT,
    THUMB_TOKEN,
    SubmitThumbnailJob,
    apply_submit_thumbnail,
    backfill_still_matches,
    hold_thumbnail_claim,
    render_submit_thumbnail,
    run_submit_thumbnail_job,
    schedule_thumbnail_retry,
    snapshot_thumbnail_due,
    thumbnail_clock,
)

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_SPEC = {"nodes": [{"id": "topic", "text": "中心"}], "connections": []}


class _Db:
    """Records commits. A rollback means a card write was lost."""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        """Count a successful card write."""
        self.commits += 1

    async def rollback(self) -> None:
        """Fail the test: these cases should not roll back."""
        raise AssertionError("rollback")


def _assignment(assignment_id: int, permissions: dict) -> LearningAssignment:
    row = LearningAssignment(
        class_id=1,
        title="作业",
        instructions="",
        template_diagram_id="tmpl-1",
        created_by=4,
        organization_id=3,
        ai_permissions=permissions,
    )
    row.id = assignment_id
    return row


def _submission(submission_id: int, snapshot: dict) -> LearningSubmission:
    row = LearningSubmission(
        assignment_id=1,
        student_user_id=9,
        organization_id=3,
        diagram_id="stu-1",
        status="submitted",
        snapshot_spec=snapshot,
    )
    row.id = submission_id
    return row


def _patch_put(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid COS and local disk. Both promote and render go through these hooks."""

    def _put(_key: str, _data: bytes, _content_type: str) -> str:
        return f"{IMAGE_REF_PREFIX}4/2026/10/thumb.png"

    monkeypatch.setattr("services.learning_space.image_storage.put_image_bytes_sync", _put)
    monkeypatch.setattr("services.learning_space.thumbnail_backfill.put_image_bytes_sync", _put)


@pytest.mark.asyncio
async def test_promotes_library_data_url_without_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """A diagram that already has a data-URL thumbnail is uploaded, not redrawn."""
    _patch_put(monkeypatch)
    assignment = _assignment(15, {})
    rendered: list[str] = []

    async def _render(_spec: dict, diagram_type: str) -> bytes:
        rendered.append(diagram_type)
        return _PNG_1X1

    async def _load(_owner: int, _diagram_id: str) -> dict:
        return {"diagram_type": "mind_map", "spec": _SPEC, "thumbnail": _PNG_DATA_URL}

    result = await fill_missing_card_thumbnails(
        _Db(),
        [assignment],
        [],
        render_png=_render,
        load_diagram=_load,
    )
    assert result["stored"] == 1
    assert result["generated"] == 0
    assert not rendered
    assert assignment.ai_permissions["template_thumbnail_ref"] == f"{IMAGE_REF_PREFIX}4/2026/10/thumb.png"


@pytest.mark.asyncio
async def test_renders_spec_when_the_card_has_no_image(monkeypatch: pytest.MonkeyPatch) -> None:
    """No stored image means render the spec and keep the PNG ref."""
    _patch_put(monkeypatch)
    assignment = _assignment(16, {})
    rendered: list[str] = []

    async def _render(_spec: dict, diagram_type: str) -> bytes:
        rendered.append(diagram_type)
        return _PNG_1X1

    async def _load(_owner: int, _diagram_id: str) -> dict:
        return {"diagram_type": "mind_map", "spec": _SPEC, "thumbnail": ""}

    result = await fill_missing_card_thumbnails(
        _Db(),
        [assignment],
        [],
        render_png=_render,
        load_diagram=_load,
    )
    assert result["generated"] == 1
    assert rendered == ["mind_map"]
    assert assignment.ai_permissions["template_thumbnail_ref"].startswith(IMAGE_REF_PREFIX)


@pytest.mark.asyncio
async def test_skips_cards_that_already_point_at_cos(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ``lsimg:`` template ref is already available."""
    _patch_put(monkeypatch)
    assignment = _assignment(17, {"template_thumbnail_ref": f"{IMAGE_REF_PREFIX}4/2026/10/keep.png"})

    async def _render(_spec: dict, _diagram_type: str) -> bytes:
        raise AssertionError("render")

    async def _load(_owner: int, _diagram_id: str) -> dict:
        raise AssertionError("load")

    result = await fill_missing_card_thumbnails(
        _Db(),
        [assignment],
        [],
        render_png=_render,
        load_diagram=_load,
    )
    assert result == {
        "stored": 0,
        "generated": 0,
        "remaining": 0,
        "failed_keys": [],
        "ready_keys": [],
    }


@pytest.mark.asyncio
async def test_one_render_leaves_the_rest_for_the_next_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Playwright stays at one card per request so the admin click can show progress."""
    _patch_put(monkeypatch)
    first = _assignment(21, {})
    second = _assignment(22, {})
    second.template_diagram_id = "tmpl-2"
    calls: list[str] = []

    async def _render(_spec: dict, _diagram_type: str) -> bytes:
        calls.append("render")
        return _PNG_1X1

    async def _load(_owner: int, diagram_id: str) -> dict:
        calls.append(diagram_id)
        return {"diagram_type": "mind_map", "spec": _SPEC}

    result = await fill_missing_card_thumbnails(
        _Db(),
        [first, second],
        [],
        render_png=_render,
        load_diagram=_load,
    )
    assert result["generated"] == 1
    assert result["remaining"] == 1
    assert calls.count("render") == 1
    assert "template_thumbnail_ref" not in (second.ai_permissions or {})


@pytest.mark.asyncio
async def test_failed_render_is_skippable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A card that cannot be drawn is reported so the next batch moves on."""
    _patch_put(monkeypatch)
    assignment = _assignment(23, {})

    async def _render(_spec: dict, _diagram_type: str) -> bytes:
        raise RuntimeError("browser down")

    async def _load(_owner: int, _diagram_id: str) -> dict:
        return {"diagram_type": "mind_map", "spec": _SPEC}

    failed = await fill_missing_card_thumbnails(
        _Db(),
        [assignment],
        [],
        render_png=_render,
        load_diagram=_load,
    )
    assert failed["failed_keys"] == ["template:23"]
    assert "template_thumbnail_ref" not in (assignment.ai_permissions or {})

    async def _timeout(_spec: dict, _diagram_type: str) -> bytes:
        raise DiagramScreenshotError("timed out")

    timed_out = await fill_missing_card_thumbnails(
        _Db(),
        [_assignment(24, {})],
        [],
        render_png=_timeout,
        load_diagram=_load,
    )
    assert timed_out["failed_keys"] == ["template:24"]

    async def _no_render(_spec: dict, _diagram_type: str) -> bytes:
        raise AssertionError("render")

    skipped = await fill_missing_card_thumbnails(
        _Db(),
        [assignment],
        [],
        skip=set(failed["failed_keys"]),
        render_png=_no_render,
        load_diagram=_load,
    )
    assert skipped["remaining"] == 0
    assert skipped["generated"] == 0


@pytest.mark.asyncio
async def test_submission_snapshot_data_url_is_uploaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Submitted homework keeps its picture by moving the data URL onto COS."""
    _patch_put(monkeypatch)
    submission = _submission(
        40,
        {"diagram_type": "mind_map", "spec": _SPEC, "thumbnail": _PNG_DATA_URL},
    )

    async def _render(_spec: dict, _diagram_type: str) -> bytes:
        raise AssertionError("render")

    async def _load(_owner: int, _diagram_id: str) -> dict:
        raise AssertionError("load")

    result = await fill_missing_card_thumbnails(
        _Db(),
        [],
        [submission],
        render_png=_render,
        load_diagram=_load,
    )
    assert result["stored"] == 1
    snap = submission.snapshot_spec
    assert isinstance(snap, dict)
    assert snap["thumbnail"] == f"{IMAGE_REF_PREFIX}4/2026/10/thumb.png"
    assert snap["spec"] == _SPEC


@pytest.mark.asyncio
async def test_commit_failure_stops_the_batch_and_drops_the_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed commit must not continue on expired rows, and the COS object is removed."""
    _patch_put(monkeypatch)
    dropped: list[list[str]] = []

    def _drop(keys: list[str]) -> None:
        dropped.append(list(keys))

    monkeypatch.setattr("services.learning_space.thumbnail_backfill.delete_stored_images_sync", _drop)

    class _FailDb:
        """Commit always fails."""

        async def commit(self) -> None:
            """Reject the write."""
            raise SQLAlchemyError("down")

        async def rollback(self) -> None:
            """Session rollback after the failed commit."""

    first = _assignment(31, {})
    second = _assignment(32, {})
    second.template_diagram_id = "tmpl-2"

    async def _render(_spec: dict, _diagram_type: str) -> bytes:
        raise AssertionError("render")

    async def _load(_owner: int, _diagram_id: str) -> dict:
        return {"diagram_type": "mind_map", "spec": _SPEC, "thumbnail": _PNG_DATA_URL}

    result = await fill_missing_card_thumbnails(
        _FailDb(),
        [first, second],
        [],
        render_png=_render,
        load_diagram=_load,
    )
    assert result["failed_keys"] == ["template:31"]
    assert result["stored"] == 0
    assert "template_thumbnail_ref" not in (second.ai_permissions or {})
    assert dropped == [["4/2026/10/thumb.png"]]


def test_submission_gap_sql_reads_thumbnail_text() -> None:
    """The scan filter asks Postgres for the thumbnail string, not the diagram spec."""
    compiled = str(select(LearningSubmission.id).where(SUBMISSION_THUMBNAIL_OPEN).compile(dialect=postgresql.dialect()))
    assert "snapshot_spec->>'thumbnail'" in compiled
    assert "snapshot_spec->>'thumb_pending'" in compiled
    assert "lsimg:%" in compiled
    assert "status IN ('submitted', 'returned')" in SUBMIT_THUMBNAIL_DUE_SQL
    assert "OR COALESCE(snapshot_spec->>'thumb_pending', '') <> ''" in SUBMIT_THUMBNAIL_DUE_SQL
    assert "thumb_retry_at" in SUBMIT_THUMBNAIL_DUE_SQL
    assert "jsonb_typeof(snapshot_spec->'spec')" in SUBMIT_THUMBNAIL_DUE_SQL


@pytest.mark.asyncio
async def test_submit_renders_diagram_thumbnail_onto_cos(monkeypatch: pytest.MonkeyPatch) -> None:
    """A background render stores a fresh PNG and does not upload the old data URL."""
    _patch_put(monkeypatch)
    rendered: list[str] = []

    async def _render(_spec: dict, diagram_type: str) -> bytes:
        rendered.append(diagram_type)
        return _PNG_1X1

    ref = await store_rendered_thumbnail(
        _SPEC,
        "mind_map",
        owner_id=9,
        render_png=_render,
    )
    assert ref.startswith(IMAGE_REF_PREFIX)
    assert rendered == ["mind_map"]

    rendered_ref = f"{IMAGE_REF_PREFIX}9/2026/10/rendered.png"

    async def _stored(*_args: object, **_kwargs: object) -> str:
        return rendered_ref

    def _put_should_not_run(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("data-url promote")

    monkeypatch.setattr("services.learning_space.thumbnail_backfill.store_rendered_thumbnail", _stored)
    monkeypatch.setattr("services.learning_space.image_storage.put_image_bytes_sync", _put_should_not_run)
    got = await render_submit_thumbnail(
        _SPEC,
        "mind_map",
        owner_id=9,
        fallback_thumb=_PNG_DATA_URL,
    )
    assert got == rendered_ref


@pytest.mark.asyncio
async def test_submit_uploads_existing_image_when_render_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed render still puts a diagram data URL on COS."""

    async def _boom(_spec: dict, _diagram_type: str) -> bytes:
        raise RuntimeError("browser down")

    assert await store_rendered_thumbnail(_SPEC, "mind_map", owner_id=9, render_png=_boom) == ""
    _patch_put(monkeypatch)

    async def _empty(*_args: object, **_kwargs: object) -> str:
        return ""

    monkeypatch.setattr("services.learning_space.thumbnail_backfill.store_rendered_thumbnail", _empty)
    got = await render_submit_thumbnail(
        _SPEC,
        "mind_map",
        owner_id=9,
        fallback_thumb=_PNG_DATA_URL,
    )
    assert got.startswith(IMAGE_REF_PREFIX)


def test_submit_row_keeps_cos_image_and_skips_data_urls() -> None:
    """The submit row must not store a data URL while the render is still running."""
    kept = stored_submit_thumbnail(None, f"{IMAGE_REF_PREFIX}9/2026/10/card.png")
    assert kept == f"{IMAGE_REF_PREFIX}9/2026/10/card.png"
    still = stored_submit_thumbnail(_PNG_DATA_URL, f"{IMAGE_REF_PREFIX}9/2026/10/card.png")
    assert still == f"{IMAGE_REF_PREFIX}9/2026/10/card.png"
    assert stored_submit_thumbnail(_PNG_DATA_URL, None) is None


def test_stale_render_does_not_replace_a_newer_submit() -> None:
    """A render for an older submit leaves the newer snapshot alone."""
    snapshot = {
        THUMB_TOKEN: "new",
        THUMB_PENDING: "new",
        THUMB_ATTEMPTS: 2,
        THUMB_RETRY_AT: "2026-11-05T08:00:00Z",
        "spec": _SPEC,
    }
    assert apply_submit_thumbnail(snapshot, "old", f"{IMAGE_REF_PREFIX}9/2026/10/old.png") is False
    assert "thumbnail" not in snapshot
    assert snapshot[THUMB_PENDING] == "new"
    assert apply_submit_thumbnail(snapshot, "new", f"{IMAGE_REF_PREFIX}9/2026/10/new.png") is True
    assert snapshot["thumbnail"] == f"{IMAGE_REF_PREFIX}9/2026/10/new.png"
    assert THUMB_PENDING not in snapshot
    assert THUMB_ATTEMPTS not in snapshot
    assert THUMB_RETRY_AT not in snapshot


@pytest.mark.asyncio
async def test_background_job_drops_image_when_submit_moved_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """A render that loses the race deletes its COS object and does not block submit."""
    dropped: list[list[str]] = []

    def _delete(keys: list[str]) -> None:
        dropped.append(keys)

    monkeypatch.setattr("services.learning_space.thumbnail_submit.delete_stored_images_sync", _delete)

    async def _miss(_submission_id: int, _token: str, _ref: str) -> bool:
        return False

    job = SubmitThumbnailJob(
        submission_id=4,
        owner_id=9,
        token="old",
        spec=_SPEC,
        diagram_type="mind_map",
        fallback_thumb=None,
        previous_ref=None,
    )

    async def _render(*_args: object, **_kwargs: object) -> str:
        return f"{IMAGE_REF_PREFIX}9/2026/10/late.png"

    monkeypatch.setattr("services.learning_space.thumbnail_submit.render_submit_thumbnail", _render)
    await run_submit_thumbnail_job(job, save=_miss)
    assert dropped == [["9/2026/10/late.png"]]


def test_pending_resubmit_stays_due_while_the_old_image_shows() -> None:
    """A kept COS image does not hide a render that never finished."""
    now = thumbnail_clock()
    old = f"{IMAGE_REF_PREFIX}9/2026/10/card.png"
    pending = {THUMB_TOKEN: "new", THUMB_PENDING: "new", "spec": _SPEC, "thumbnail": old}
    assert snapshot_thumbnail_due(pending, now) is True
    finished = {THUMB_TOKEN: "new", "spec": _SPEC, "thumbnail": old}
    assert snapshot_thumbnail_due(finished, now) is False
    waiting = {
        THUMB_TOKEN: "new",
        THUMB_PENDING: "new",
        THUMB_RETRY_AT: "2999-01-01T00:00:00Z",
        "spec": _SPEC,
    }
    assert snapshot_thumbnail_due(waiting, now) is False
    assert snapshot_thumbnail_due({"spec": "not-a-diagram", THUMB_PENDING: "new"}, now) is False


def test_failed_render_records_a_later_retry() -> None:
    """The same submit stays queued, and the next try waits."""
    snapshot = {THUMB_TOKEN: "tok", THUMB_PENDING: "tok", "spec": _SPEC}
    now = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
    assert schedule_thumbnail_retry(snapshot, "older", now) is False
    assert schedule_thumbnail_retry(snapshot, "tok", now) is True
    assert snapshot[THUMB_ATTEMPTS] == 1
    assert snapshot[THUMB_RETRY_AT] == "2026-11-05T08:00:15Z"
    assert snapshot[THUMB_PENDING] == "tok"
    assert schedule_thumbnail_retry(snapshot, "tok", now) is True
    assert snapshot[THUMB_ATTEMPTS] == 2
    assert snapshot[THUMB_RETRY_AT] == "2026-11-05T08:01:00Z"


def test_claim_lease_hides_the_row_until_it_expires() -> None:
    """A row being drawn is not due again until the lease time."""
    snapshot = {THUMB_TOKEN: "tok", THUMB_PENDING: "tok", "spec": _SPEC}
    now = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
    assert hold_thumbnail_claim(snapshot, "tok", now, 180) is True
    assert snapshot[THUMB_RETRY_AT] == "2026-11-05T08:03:00Z"
    assert snapshot_thumbnail_due(snapshot, thumbnail_clock(now)) is False
    assert snapshot_thumbnail_due(snapshot, "2026-11-05T08:03:00Z") is True


def test_finished_submit_is_not_queued_again() -> None:
    """A PNG that already landed is not replaced or put back on the queue."""
    now = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
    done = f"{IMAGE_REF_PREFIX}9/2026/10/done.png"
    snapshot = {THUMB_TOKEN: "tok", "spec": _SPEC, "thumbnail": done}
    assert schedule_thumbnail_retry(snapshot, "tok", now) is False
    assert THUMB_PENDING not in snapshot
    late = f"{IMAGE_REF_PREFIX}9/2026/10/late.png"
    assert apply_submit_thumbnail(snapshot, "tok", late) is False
    assert snapshot["thumbnail"] == done
    assert backfill_still_matches(snapshot, "tok") is False
    assert backfill_still_matches({THUMB_TOKEN: "tok", "spec": _SPEC}, "tok") is True


@pytest.mark.asyncio
async def test_missing_render_asks_for_a_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A render that produces no image leaves the submission queued."""
    noted: list[int] = []

    async def _note(job: SubmitThumbnailJob) -> None:
        noted.append(job.submission_id)

    async def _render(*_args: object, **_kwargs: object) -> str:
        return ""

    monkeypatch.setattr("services.learning_space.thumbnail_submit.render_submit_thumbnail", _render)
    job = SubmitThumbnailJob(
        submission_id=8,
        owner_id=9,
        token="tok",
        spec=_SPEC,
        diagram_type="mind_map",
        fallback_thumb=None,
        previous_ref=None,
    )
    await run_submit_thumbnail_job(job, note_failure=_note)
    assert noted == [8]


@pytest.mark.asyncio
async def test_pending_cos_thumbnail_is_rendered_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resubmit keeps the old card image and still asks for a new PNG."""
    _patch_put(monkeypatch)
    dropped: list[list[str]] = []

    def _drop(keys: list[str]) -> None:
        dropped.append(list(keys))

    monkeypatch.setattr("services.learning_space.thumbnail_backfill.delete_stored_images_sync", _drop)
    old = f"{IMAGE_REF_PREFIX}9/2026/10/old.png"
    submission = _submission(
        41,
        {
            "diagram_type": "mind_map",
            "spec": _SPEC,
            "thumbnail": old,
            THUMB_TOKEN: "tok",
            THUMB_PENDING: "tok",
        },
    )
    rendered: list[str] = []

    async def _render(_spec: dict, diagram_type: str) -> bytes:
        rendered.append(diagram_type)
        return _PNG_1X1

    async def _load(_owner: int, _diagram_id: str) -> dict:
        return {"diagram_type": "mind_map", "spec": _SPEC}

    result = await fill_missing_card_thumbnails(
        _Db(),
        [],
        [submission],
        render_png=_render,
        load_diagram=_load,
    )
    assert result["generated"] == 1
    assert rendered == ["mind_map"]
    snap = submission.snapshot_spec
    assert isinstance(snap, dict)
    assert snap["thumbnail"] == f"{IMAGE_REF_PREFIX}4/2026/10/thumb.png"
    assert THUMB_PENDING not in snap
    assert dropped == [["9/2026/10/old.png"]]
