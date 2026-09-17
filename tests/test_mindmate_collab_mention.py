"""MindMate collab @mention detection."""

from __future__ import annotations

from services.features.mindmate_collab.mention import (
    extract_mindmate_query,
    message_mentions_mindmate,
)


def test_message_mentions_mindmate_plain_and_bold() -> None:
    """@MindMate and @**MindMate** both trigger the AI."""
    assert message_mentions_mindmate("@MindMate 帮我写教案") is True
    assert message_mentions_mindmate("@**MindMate** 帮我写教案") is True
    assert message_mentions_mindmate("只给老师看") is False
    assert message_mentions_mindmate("@mindmatexyz") is False


def test_message_mentions_school_agent_alias() -> None:
    """School-branded agent names are accepted as aliases."""
    assert message_mentions_mindmate("@迈特教研 帮我写教案", ("迈特教研",)) is True
    assert message_mentions_mindmate("帮我写教案", ("迈特教研",)) is False


def test_extract_mindmate_query_strips_tokens() -> None:
    """Mention tokens are removed before the Dify prompt."""
    assert extract_mindmate_query("@MindMate 帮我写教案") == "帮我写教案"
    assert extract_mindmate_query("@**MindMate** 帮我写教案") == "帮我写教案"
    assert extract_mindmate_query("@迈特教研 帮我写教案", ("迈特教研",)) == "帮我写教案"
