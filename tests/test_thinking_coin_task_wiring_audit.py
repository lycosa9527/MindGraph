"""Audit: every seeded earn task is wired to a runtime credit path."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.thinking_coin_wiring_manifest import (
    ALL_SEEDED_SLUGS,
    CLIENT_EVENT_TASKS,
    TASK_WIRING,
    TaskWiring,
    USAGE_DAILY_TASKS,
)
from utils.auth.thinking_coin_config import HANDLER_CLIENT_EVENT

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_SRC = _REPO_ROOT / "frontend" / "src"


def _read(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _frontend_contains(marker: str) -> bool:
    for path in _FRONTEND_SRC.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".ts", ".vue"}:
            continue
        if marker.endswith((".ts", ".vue")) and path.name == marker:
            return True
        if marker in path.read_text(encoding="utf-8"):
            return True
    return False


def _backend_contains(marker: str) -> bool:
    if marker.startswith("routers/") or marker.startswith("services/"):
        return marker in _read(marker)
    search_roots = (_REPO_ROOT / "routers", _REPO_ROOT / "services")
    for root in search_roots:
        for path in root.rglob("*.py"):
            if marker in path.read_text(encoding="utf-8"):
                return True
    return False


def test_manifest_covers_all_seeded_slugs() -> None:
    """Every slug inserted by Alembic 0065/0068/0069 appears in the manifest."""
    manifest_slugs = {task.slug for task in TASK_WIRING}
    assert manifest_slugs == ALL_SEEDED_SLUGS


def test_migration_files_list_same_slugs() -> None:
    """Alembic seed files still mention every manifest slug."""
    migration_text = "\n".join(
        _read(path)
        for path in (
            "alembic/versions/rev_0065_thinking_coins.py",
            "alembic/versions/rev_0068_thinking_coin_exploration_tasks.py",
            "alembic/versions/rev_0069_thinking_coin_more_exploration_tasks.py",
        )
    )
    for slug in ALL_SEEDED_SLUGS:
        assert f'"slug": "{slug}"' in migration_text or f"'slug': '{slug}'" in migration_text


def test_client_event_keys_unique_and_match_constants() -> None:
    """Each client_event task maps to a distinct event_key constant."""
    keys = [task.event_key for task in CLIENT_EVENT_TASKS]
    assert len(keys) == len(set(keys))
    assert all(key for key in keys)


@pytest.mark.parametrize("task", TASK_WIRING, ids=lambda task: task.slug)
def test_task_backend_markers_present(task: TaskWiring) -> None:
    """Backend code references each task's credit entry points."""
    for marker in task.backend_markers:
        assert _backend_contains(marker), f"{task.slug}: missing backend marker {marker!r}"


@pytest.mark.parametrize("task", TASK_WIRING, ids=lambda task: task.slug)
def test_task_frontend_markers_when_required(task: TaskWiring) -> None:
    """User-visible tasks propagate thinking_coins footer to the UI."""
    if not task.frontend_markers:
        return
    for marker in task.frontend_markers:
        assert _frontend_contains(marker), f"{task.slug}: missing frontend marker {marker!r}"


@pytest.mark.parametrize("task", TASK_WIRING, ids=lambda task: task.slug)
def test_credit_expectation_matches_handler(task: TaskWiring) -> None:
    """Only navigate/referral deferred tasks skip wallet credit."""
    if task.credits_on_complete:
        assert task.handler_key != "navigate"
        assert task.note == "" or "not implemented" not in task.note.lower()
    else:
        assert task.slug in {"publish_case", "referral_register"}


def test_mindmate_collab_join_loads_org_before_track() -> None:
    """Workshop join earn must load org — passing None skips trial credits."""
    source = _read("routers/api/mindmate_collab_routes.py")
    assert "load_user_org(current_user)" in source
    assert "track_client_event(db, current_user, None" not in source


def test_client_event_handler_routes_load_org() -> None:
    """Inline client_event routes resolve org before eligibility checks."""
    for rel_path in (
        "routers/api/activity.py",
        "routers/api/diagrams.py",
        "routers/api/diagrams_workshop_routes.py",
        "routers/api/mindmate_collab_routes.py",
        "routers/api/canvas_translate.py",
    ):
        source = _read(rel_path)
        assert "load_user_org" in source, f"{rel_path} must load org for thinking coins"


@pytest.mark.parametrize("task", USAGE_DAILY_TASKS, ids=lambda task: task.slug)
def test_usage_daily_tasks_have_request_type(task: TaskWiring) -> None:
    """usage_daily tasks declare request_type for matcher."""
    assert task.request_type


@pytest.mark.parametrize("task", CLIENT_EVENT_TASKS, ids=lambda task: task.slug)
def test_client_event_tasks_have_event_key(task: TaskWiring) -> None:
    """client_event tasks declare event_key for matcher."""
    assert task.event_key
    assert task.handler_key == HANDLER_CLIENT_EVENT
