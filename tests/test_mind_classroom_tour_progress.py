"""Sticky merge for parallel canvas-tour job progress."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from services.mind_classroom import canvas_tour as tour_mod
from services.mind_classroom import tour_progress as tour_progress_mod
from services.mind_classroom.outline import ClassroomJobRejected
from services.mind_classroom.tour_progress import merge_tour_progress, patch_tour_progress, seed_branch_slots


def test_seed_branch_slots_are_pending() -> None:
    """Each family starts pending so the button can name the first one."""
    slots = seed_branch_slots(["光合作用", "呼吸作用"])
    assert [slot["index"] for slot in slots] == [1, 2]
    assert slots[0]["state"] == "pending"
    assert slots[1]["label"] == "呼吸作用"


def test_merge_keeps_tts_ready_when_another_branch_streams() -> None:
    """A late first-token must not wipe first-branch TTS unlock."""
    seeded = merge_tour_progress(None, phase="script_parallel", seed_labels=["开场", "第二支"])
    first_ready = merge_tour_progress(
        seeded,
        phase="first_branch",
        branch=1,
        branch_state="done",
        branch_label="开场",
        tts_ready=True,
        step_count=3,
    )
    late_stream = merge_tour_progress(
        first_ready,
        phase="llm_streaming",
        branch=2,
        branch_state="streaming",
        branch_label="第二支",
        chars=40,
        tts_ready=False,
    )
    assert late_stream["tts_ready"] is True
    assert late_stream["step_count"] == 3
    assert late_stream["done"] == 1
    assert late_stream["in_flight"] == 1
    assert late_stream["branch_label"] == "第二支"
    assert late_stream["branches"][0]["state"] == "done"
    assert late_stream["branches"][1]["state"] == "streaming"


def test_merge_display_prefers_lowest_streaming_not_last_writer() -> None:
    """Button name stays on the first still-writing family."""
    seeded = merge_tour_progress(
        None,
        phase="script_parallel",
        seed_labels=["第一支", "第二支", "第三支"],
    )
    second = merge_tour_progress(
        seeded,
        phase="llm_streaming",
        branch=2,
        branch_state="streaming",
        branch_label="第二支",
    )
    first = merge_tour_progress(
        second,
        phase="llm_streaming",
        branch=1,
        branch_state="streaming",
        branch_label="第一支",
    )
    assert first["branch"] == 1
    assert first["branch_label"] == "第一支"


def test_merge_does_not_regress_done_to_streaming() -> None:
    """A delayed stream publish cannot reopen a finished family."""
    done = merge_tour_progress(
        merge_tour_progress(None, phase="script_parallel", seed_labels=["开场"]),
        phase="first_branch",
        branch=1,
        branch_state="done",
        tts_ready=True,
    )
    replay = merge_tour_progress(
        done,
        phase="llm_streaming",
        branch=1,
        branch_state="streaming",
        chars=12,
    )
    assert replay["branches"][0]["state"] == "done"
    assert replay["tts_ready"] is True


def test_tour_progress_has_no_process_lock() -> None:
    """Progress merge must not keep an asyncio.Lock across Celery event loops."""
    assert "asyncio.Lock" not in inspect.getsource(tour_progress_mod)


class _JobRow:
    """In-memory job row the repository can lock and patch."""

    def __init__(self) -> None:
        self.status = "generating"
        self.current_stage = "script"
        self.celery_task_id = "cel-1"
        self.progress: dict[str, Any] = {"phase": "script"}
        self.attempt_count = 0
        self.attempts: list[dict[str, Any]] = []
        self.started_at = None
        self.finished_at = None
        self.updated_at = None
        self.error_message = None
        self.result_json = None
        self.lesson_plan_json = None


class _ExecuteResult:
    def __init__(self, row: _JobRow) -> None:
        self._row = row

    def scalar_one_or_none(self) -> _JobRow:
        """Return the locked row."""
        return self._row


class _Session:
    def __init__(self, row: _JobRow) -> None:
        self.row = row
        self.statements: list[Any] = []
        self.commits = 0

    async def execute(self, stmt: Any) -> _ExecuteResult:
        """Record the SELECT used to lock the job."""
        self.statements.append(stmt)
        return _ExecuteResult(self.row)

    async def get(self, _model: Any, _job_id: str) -> _JobRow:
        """Return the row already locked in this session."""
        return self.row

    async def flush(self) -> None:
        """Flush is a no-op for the fake."""

    async def commit(self) -> None:
        """Count commits from the one locked session."""
        self.commits += 1

    async def refresh(self, _row: _JobRow) -> None:
        """Refresh is a no-op for the fake."""


@pytest.mark.asyncio
async def test_patch_tour_progress_locks_and_commits_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parallel progress writes share one FOR UPDATE and one commit."""
    row = _JobRow()
    session = _Session(row)
    published: list[str] = []

    @asynccontextmanager
    async def _open() -> AsyncIterator[_Session]:
        yield session

    async def _publish(job_id: str) -> None:
        published.append(job_id)

    monkeypatch.setattr(tour_progress_mod, "system_rls_session", _open)
    monkeypatch.setattr(tour_progress_mod, "publish_classroom_job_snapshot", _publish)

    first = await patch_tour_progress(
        "job-1",
        celery_task_id="cel-1",
        status="generating",
        stage="llm_streaming",
        phase="llm_streaming",
        branch=1,
        branch_state="streaming",
        branch_label="开场",
        chars=4,
    )
    second = await patch_tour_progress(
        "job-1",
        celery_task_id="cel-1",
        status="generating",
        stage="llm_streaming",
        phase="llm_streaming",
        branch=2,
        branch_state="streaming",
        branch_label="第二支",
        chars=8,
    )
    assert session.commits == 2
    assert len(session.statements) == 2
    assert all("FOR UPDATE" in str(stmt.compile()) for stmt in session.statements)
    assert published == ["job-1", "job-1"]
    labels = [slot["label"] for slot in second["branches"]]
    assert labels == ["开场", "第二支"]
    assert first["branches"][0]["state"] == "streaming"
    assert second["in_flight"] == 2


@pytest.mark.asyncio
async def test_center_only_map_fails_without_exception_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """A topic-only map fails the job with a warning, not logger.exception."""

    class _Job:
        status = "queued"
        spec_snapshot = {"topic": "只有主题"}
        settings: dict[str, Any] = {}
        user_id = 1
        organization_id = 1
        diagram_id = None

    class _Repo:
        def __init__(self, db: object) -> None:
            self.db = db

        async def claim_for_run(self, job_id: str, celery_task_id: str | None = None) -> _Job:
            """Return the queued center-only job."""
            assert job_id
            assert celery_task_id is None or isinstance(celery_task_id, str)
            return _Job()

    @asynccontextmanager
    async def _open() -> AsyncIterator[object]:
        yield object()

    marked: list[BaseException] = []
    tracebacks: list[str] = []

    async def _mark(job_id: str, exc: BaseException, celery_task_id: str | None = None) -> None:
        assert job_id
        assert celery_task_id is None or isinstance(celery_task_id, str)
        marked.append(exc)

    async def _lease(*_args: object, **_kwargs: object) -> str:
        return "planning"

    async def _stage(*_args: object, **_kwargs: object) -> None:
        return None

    def _log(*_args: object, **_kwargs: object) -> None:
        return None

    def _exception(message: str, *_args: object, **_kwargs: object) -> None:
        tracebacks.append(message)

    monkeypatch.setattr(tour_mod, "system_rls_session", _open)
    monkeypatch.setattr(tour_mod, "MindClassroomJobRepository", _Repo)
    monkeypatch.setattr(tour_mod, "require_run_lease", _lease)
    monkeypatch.setattr(tour_mod, "mark_job_stage", _stage)
    monkeypatch.setattr(tour_mod, "log_job_stage", _log)
    monkeypatch.setattr(tour_mod, "mark_terminal_from_error", _mark)
    monkeypatch.setattr(tour_mod.logger, "exception", _exception)

    finished = await tour_mod.run_canvas_tour_job("job-center")
    assert finished is False
    assert len(marked) == 1
    assert isinstance(marked[0], ClassroomJobRejected)
    assert not tracebacks
