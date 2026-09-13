"""DM history includes sender identity for the chat bubble."""

from __future__ import annotations

from types import SimpleNamespace

from models.domain.workshop_chat import DirectMessage
from services.features.workshop_chat.dm_service import _format_dm
from tests.typing_helpers import as_type


def test_dm_history_includes_sender_name() -> None:
    """History rows must match the send payload's sender fields."""
    sender = SimpleNamespace(name="林老师", avatar="/a.png")
    msg = SimpleNamespace(
        id=3,
        sender_id=9,
        sender=sender,
        recipient_id=2,
        content="hi",
        message_type="text",
        is_read=False,
        mentioned_user_ids=None,
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        edited_at=None,
    )
    formatted = _format_dm(as_type(msg, DirectMessage))
    assert formatted["sender_name"] == "林老师"
    assert formatted["sender_avatar"] == "/a.png"
    assert formatted["sender_id"] == 9
