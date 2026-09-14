"""DM history includes sender identity for the chat bubble."""

from __future__ import annotations

from types import SimpleNamespace

from models.domain.auth import User
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


def test_dm_format_uses_explicit_sender_when_relation_missing() -> None:
    """Send path passes the already-loaded sender so WS/toasts get a name."""
    sender = SimpleNamespace(name="王老师", avatar="🦊")
    msg = SimpleNamespace(
        id=4,
        sender_id=11,
        sender=None,
        recipient_id=2,
        content="ping",
        message_type="text",
        is_read=False,
        mentioned_user_ids=None,
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        edited_at=None,
    )
    formatted = _format_dm(as_type(msg, DirectMessage), sender=as_type(sender, User))
    assert formatted["sender_name"] == "王老师"
    assert formatted["sender_avatar"] == "🦊"


def test_dm_format_blank_name_falls_back_without_empty_label() -> None:
    """Whitespace-only names must not become a blank toast or bubble label."""
    sender = SimpleNamespace(name="  ", avatar=None)
    msg = SimpleNamespace(
        id=5,
        sender_id=8,
        sender=sender,
        recipient_id=2,
        content="x",
        message_type="text",
        is_read=False,
        mentioned_user_ids=None,
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        edited_at=None,
    )
    formatted = _format_dm(as_type(msg, DirectMessage))
    assert formatted["sender_name"] == "User 8"
