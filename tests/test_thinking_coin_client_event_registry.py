"""Tests for task registry client event helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.auth.thinking_coin.task_registry import (
    task_client_event_key,
    tasks_for_client_event,
)
from utils.auth.thinking_coin_config import HANDLER_CLIENT_EVENT


def test_task_client_event_key_reads_config() -> None:
    """event_key is parsed from action_config."""
    task = MagicMock()
    task.action_config = {"event_key": "diagram_export"}
    assert task_client_event_key(task) == "diagram_export"


def test_tasks_for_client_event_filters_active() -> None:
    """Only active client_event tasks with matching key are returned."""
    match = MagicMock()
    match.is_active = True
    match.handler_key = HANDLER_CLIENT_EVENT
    match.action_config = {"event_key": "mindmate_share"}

    other = MagicMock()
    other.is_active = True
    other.handler_key = HANDLER_CLIENT_EVENT
    other.action_config = {"event_key": "diagram_export"}

    rows = tasks_for_client_event([match, other], "mindmate_share")
    assert rows == [match]
