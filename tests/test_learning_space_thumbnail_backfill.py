"""Admin scan stores missing Learning Space card thumbnails on COS."""

from __future__ import annotations

import pytest

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from models.domain.learning_space import LearningAssignment, LearningSubmission
from services.learning_space.image_storage import IMAGE_REF_PREFIX
from services.learning_space.thumbnail_backfill import fill_missing_card_thumbnails
from services.learning_space.thumbnail_backfill_scan import SUBMISSION_THUMBNAIL_OPEN
from services.learning_space.thumbnail_storage import submit_thumbnail_source

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
    assert "lsimg:%" in compiled


def test_submit_keeps_cos_thumbnail_when_diagram_has_none() -> None:
    """Resubmit must not drop a backfilled COS image when the library thumbnail is empty."""
    kept = submit_thumbnail_source(None, f"{IMAGE_REF_PREFIX}9/2026/10/card.png")
    assert kept == f"{IMAGE_REF_PREFIX}9/2026/10/card.png"
    fresh = submit_thumbnail_source(_PNG_DATA_URL, f"{IMAGE_REF_PREFIX}9/2026/10/card.png")
    assert fresh == _PNG_DATA_URL
