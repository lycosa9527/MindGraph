"""MindMate collab shared message history persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from models.domain.mindmate_collab import MindmateCollabMessage
from services.features.mindmate_collab.message_history import (
    normalize_seed_messages,
    serialize_message_row,
)


def test_normalize_seed_messages_clamps_user_sender_to_host() -> None:
    """User seed rows always attribute messages to the room host."""
    normalized, error = normalize_seed_messages(
        [{"role": "user", "content": "Hello", "sender_user_id": 999}],
        owner_user_id=42,
    )
    assert error is None
    assert normalized == [{"role": "user", "content": "Hello", "sender_user_id": 42}]


def test_normalize_seed_messages_defaults_user_sender_to_host() -> None:
    """Host thread user rows inherit the host user id when sender is omitted."""
    normalized, error = normalize_seed_messages(
        [{"role": "user", "content": "Hello team"}],
        owner_user_id=42,
    )
    assert error is None
    assert normalized == [{"role": "user", "content": "Hello team", "sender_user_id": 42}]


def test_normalize_seed_messages_rejects_invalid_role() -> None:
    """Only user and assistant roles may be seeded into a room."""
    normalized, error = normalize_seed_messages(
        [{"role": "system", "content": "ignored"}],
        owner_user_id=1,
    )
    assert normalized is None
    assert error == "Invalid seed message role"


def test_serialize_message_row_includes_username_for_user_messages() -> None:
    """History payloads expose a display label for teacher messages."""
    row = MindmateCollabMessage(
        id=7,
        session_id="session-1",
        role="user",
        content="Question",
        sender_user_id=3,
        created_at=datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
    )
    payload = serialize_message_row(row, "Teacher Li", None, None)
    assert payload["username"] == "Teacher Li"
    assert payload["id"] == 7
