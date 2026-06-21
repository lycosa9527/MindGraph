"""Tests for usage_daily task context matching."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.auth.thinking_coin.task_registry import (
    task_usage_context_matches,
    tasks_for_request_type,
)
from utils.auth.thinking_coin_config import HANDLER_USAGE_DAILY


def _usage_task(slug: str, request_type: str, **flags: object) -> MagicMock:
    task = MagicMock()
    task.slug = slug
    task.is_active = True
    task.handler_key = HANDLER_USAGE_DAILY
    task.action_config = {"request_type": request_type, **flags}
    return task


def test_tasks_for_request_type_excludes_learning_sheet_without_context() -> None:
    """Learning-sheet-only tasks require explicit context."""
    plain = _usage_task("daily_diagram_ai", "diagram_generation")
    sheet = _usage_task("daily_learning_sheet_ai", "diagram_generation", is_learning_sheet=True)

    matched = tasks_for_request_type([plain, sheet], "diagram_generation")
    assert matched == [plain]


def test_tasks_for_request_type_matches_learning_sheet_context() -> None:
    """Learning-sheet task matches when context flag is true."""
    plain = _usage_task("daily_diagram_ai", "diagram_generation")
    sheet = _usage_task("daily_learning_sheet_ai", "diagram_generation", is_learning_sheet=True)

    matched = tasks_for_request_type(
        [plain, sheet],
        "diagram_generation",
        is_learning_sheet=True,
    )
    assert matched == [plain, sheet]


def test_task_usage_context_matches_bool_flag() -> None:
    """Context matcher compares is_learning_sheet when configured."""
    task = _usage_task("daily_learning_sheet_ai", "diagram_generation", is_learning_sheet=True)
    assert task_usage_context_matches(task, is_learning_sheet=True) is True
    assert task_usage_context_matches(task, is_learning_sheet=False) is False
    assert task_usage_context_matches(task, is_learning_sheet=None) is False
