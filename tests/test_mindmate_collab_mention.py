"""MindMate collab @mention detection."""

from __future__ import annotations

from types import SimpleNamespace

from services.features.mindmate_collab.mention import (
    collab_message_targets_mindmate,
    extract_mindmate_query,
    mention_aliases_from_org,
    message_mentions_mindmate,
)


def test_message_mentions_mindmate_plain_and_bold() -> None:
    """@MindMate and @**MindMate** both trigger the AI."""
    assert message_mentions_mindmate("@MindMate 帮我写教案") is True
    assert message_mentions_mindmate("@**MindMate** 帮我写教案") is True
    assert message_mentions_mindmate("只给老师看") is False
    assert message_mentions_mindmate("@mindmatexyz") is False
    assert message_mentions_mindmate("@mindmate1") is False


def test_message_mentions_school_agent_alias() -> None:
    """School-branded agent names are accepted as aliases."""
    assert message_mentions_mindmate("@迈特教研 帮我写教案", ("迈特教研",)) is True
    assert message_mentions_mindmate("帮我写教案", ("迈特教研",)) is False


def test_mention_aliases_from_org_uses_name_and_alias() -> None:
    """@-mentions follow the saved agent name and 小名, not the user row."""
    org = SimpleNamespace(mindmate_agent_name="八一思行者", mindmate_agent_alias=" 小思 ")
    assert mention_aliases_from_org(org) == ("八一思行者", "小思")
    assert message_mentions_mindmate("@小思 你好", mention_aliases_from_org(org)) is True
    blank = SimpleNamespace(mindmate_agent_name="  ", mindmate_agent_alias=None)
    assert not mention_aliases_from_org(blank)


def test_mention_accepts_cjk_after_mindmate_and_rejects_email() -> None:
    """@mindmate can sit against Chinese text. An email address is not a mention."""
    assert message_mentions_mindmate("@mindmate帮我写教案") is True
    assert message_mentions_mindmate("请@MindMate看一下") is True
    assert message_mentions_mindmate("＠mindmate 你好") is True
    assert message_mentions_mindmate("联系 user@mindmate.com") is False
    assert message_mentions_mindmate("@小思你好", ("小思",)) is False
    assert message_mentions_mindmate("@小思，你好", ("小思",)) is True


def test_segment_routes_to_mindmate_and_everyone_still_accepts_mention() -> None:
    """MindMate segment always asks the AI. Everyone does only on @mindmate."""
    assert collab_message_targets_mindmate(True, "只给老师看") is True
    assert collab_message_targets_mindmate(True, "联系 user@mindmate.com") is True
    assert collab_message_targets_mindmate(False, "只给老师看") is False
    assert collab_message_targets_mindmate(False, "@mindmate帮我写教案") is True
    assert collab_message_targets_mindmate("false", "@mindmate帮我写教案") is True
    assert collab_message_targets_mindmate("true", "只给老师看") is False
    assert collab_message_targets_mindmate(None, "帮我写教案", ("迈特教研",)) is False
    assert collab_message_targets_mindmate(None, "@迈特教研 帮我", ("迈特教研",)) is True


def test_extract_mindmate_query_strips_tokens() -> None:
    """Mention tokens are removed before the Dify prompt."""
    assert extract_mindmate_query("@MindMate 帮我写教案") == "帮我写教案"
    assert extract_mindmate_query("@**MindMate** 帮我写教案") == "帮我写教案"
    assert extract_mindmate_query("@迈特教研 帮我写教案", ("迈特教研",)) == "帮我写教案"
    assert extract_mindmate_query("@mindmate帮我写教案") == "帮我写教案"
    assert extract_mindmate_query("请@MindMate看一下") == "请看一下"
