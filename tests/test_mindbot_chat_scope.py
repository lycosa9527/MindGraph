"""Tests for DingTalk chat scope classification (internal vs cross-org group)."""

from __future__ import annotations

import main as _main_app

assert _main_app.app.title

from services.mindbot.education.metrics import dingtalk_chat_scope
from services.mindbot.platforms.dingtalk.cards.ai_card_create import is_cross_org_group_body


def test_cross_org_group_body_detected() -> None:
    """LWCP-only group senders are cross-org, not internal group scope."""
    body = {
        "conversationType": "2",
        "conversationId": "cidCrossOrgGroup",
        "senderId": "$:LWCP_v1:$abc",
    }
    assert is_cross_org_group_body(body) is True
    assert dingtalk_chat_scope(body) == "cross_org_group"


def test_internal_group_scope() -> None:
    """Normal staff id in a group is internal group scope."""
    body = {
        "conversationType": "2",
        "conversationId": "cidInternalGroup",
        "senderStaffId": "manager7439",
    }
    assert is_cross_org_group_body(body) is False
    assert dingtalk_chat_scope(body) == "group"
