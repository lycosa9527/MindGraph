"""Workshop chat RLS: session GUC plus policy SQL for topic-less rows and DMs."""

from utils.db.rls_context import RlsContext
from utils.db_rls.policy_builder import (
    WORKSHOP_CHILD,
    WORKSHOP_MESSAGE_EXPR,
    WORKSHOP_STAR_EXPR,
    WORKSHOP_TOPIC_PREF_EXPR,
)


class _User:
    """Minimal user for RlsContext.from_user."""

    id = 1
    organization_id = 10
    role = "teacher"


def test_allow_global_channels_flag() -> None:
    """Announce (org-null) needs the global-channel GUC on teacher sessions."""
    ctx = RlsContext.from_user(_User(), allow_global_channels=True)
    assert ctx.session_vars()["allow_global_channels"] == "1"


def test_workshop_message_rls_uses_channel_not_topic() -> None:
    """Main-stream messages have topic_id NULL; policy must not join chat_topics."""
    expr = dict(WORKSHOP_CHILD)["chat_messages"]
    assert expr == WORKSHOP_MESSAGE_EXPR
    assert "chat_topics" not in expr
    assert "c.id = channel_id" in expr
    assert "rls_chat_channel_visible" in expr


def test_workshop_reaction_rls_uses_message_channel() -> None:
    """Reactions follow the message's channel, including topic-less rows."""
    expr = dict(WORKSHOP_CHILD)["message_reactions"]
    assert "m.channel_id" in expr
    assert "chat_topics" not in expr


def test_workshop_attachment_rls_covers_dm_and_channel() -> None:
    """Channel files walk message.channel_id; DM files walk dm_id."""
    expr = dict(WORKSHOP_CHILD)["file_attachments"]
    assert "dm_id" in expr
    assert "direct_messages" in expr
    assert "message_id" in expr
    assert "chat_topics" not in expr
    assert "rls_user_visible(d.sender_id)" in expr
    assert "uploader_id = rls_current_user_id()" in expr
    assert "message_id IS NULL AND dm_id IS NULL" in expr


def test_workshop_star_rls_requires_visible_message() -> None:
    """Stars cannot point at another school's message_id."""
    expr = dict(WORKSHOP_CHILD)["starred_messages"]
    assert expr == WORKSHOP_STAR_EXPR
    assert "rls_user_visible(user_id)" in expr
    assert "m.channel_id" in expr
    assert "rls_chat_channel_visible" in expr


def test_workshop_topic_pref_rls_requires_visible_topic() -> None:
    """Mute/pin prefs cannot target another school's topic_id."""
    expr = dict(WORKSHOP_CHILD)["user_topic_preferences"]
    assert expr == WORKSHOP_TOPIC_PREF_EXPR
    assert "rls_user_visible(user_id)" in expr
    assert "chat_topics" in expr
    assert "rls_chat_channel_visible" in expr
