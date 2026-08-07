"""Celery lease fencing for ZhiHui diagram lesson decks."""

from __future__ import annotations

import pytest

from services.zhihui.lesson_lease import LeaseLost, require_run_lease, set_status_with_lease


class _FakeConv:
    def __init__(self, *, status: str = "generating", celery_task_id: str | None = "task-a"):
        self.status = status
        self.celery_task_id = celery_task_id


class _FakeRepo:
    def __init__(self, row: _FakeConv | None):
        self.row = row
        self.updates: list[dict] = []

    async def get_by_uuid(self, _conversation_id: str):
        """Return the fake conversation row."""
        return self.row

    async def update_conversation(self, conversation_id: str, **kwargs):
        """Record an update attempt."""
        self.updates.append({"conversation_id": conversation_id, **kwargs})
        return self.row


def _patch_repo(monkeypatch: pytest.MonkeyPatch, repo: _FakeRepo) -> None:
    class _Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr("services.zhihui.lesson_lease.system_rls_session", _Session)
    monkeypatch.setattr(
        "services.zhihui.lesson_lease.ZhihuiConversationRepository",
        lambda _db: repo,
    )


@pytest.mark.asyncio
async def test_require_run_lease_accepts_matching_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Matching celery_task_id keeps the run alive."""
    repo = _FakeRepo(_FakeConv(celery_task_id="task-a"))
    _patch_repo(monkeypatch, repo)
    status = await require_run_lease("conv-1", celery_task_id="task-a")
    assert status == "generating"


@pytest.mark.asyncio
async def test_require_run_lease_rejects_mismatched_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """A newer Celery task id supersedes this run."""
    repo = _FakeRepo(_FakeConv(celery_task_id="task-b"))
    _patch_repo(monkeypatch, repo)
    with pytest.raises(LeaseLost, match="celery lease lost"):
        await require_run_lease("conv-1", celery_task_id="task-a")


@pytest.mark.asyncio
async def test_require_run_lease_rejects_stop_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancelled/failed/partial stops the worker without rewriting status."""
    repo = _FakeRepo(_FakeConv(status="cancelled", celery_task_id="task-a"))
    _patch_repo(monkeypatch, repo)
    with pytest.raises(LeaseLost, match="status=cancelled"):
        await require_run_lease("conv-1", celery_task_id="task-a")


@pytest.mark.asyncio
async def test_set_status_skips_when_lease_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Superseded workers must not mutate conversation status."""
    repo = _FakeRepo(_FakeConv(celery_task_id="task-b"))
    _patch_repo(monkeypatch, repo)
    with pytest.raises(LeaseLost, match="celery lease lost"):
        await set_status_with_lease(
            "conv-1",
            status="complete",
            celery_task_id="task-a",
        )
    assert not repo.updates
