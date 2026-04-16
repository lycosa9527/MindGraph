"""MindBot effective chain-of-thought flags by DingTalk chat type."""

from __future__ import annotations

from types import SimpleNamespace

from services.mindbot.core.chain_of_thought_policy import effective_show_chain_of_thought


def test_effective_cot_oto() -> None:
    cfg = SimpleNamespace(
        show_chain_of_thought_oto=True,
        show_chain_of_thought_internal_group=False,
        show_chain_of_thought_cross_org_group=False,
    )
    body = {"conversationType": "1", "senderStaffId": "s1"}
    assert effective_show_chain_of_thought(cfg, body) is True


def test_effective_cot_internal_group() -> None:
    cfg = SimpleNamespace(
        show_chain_of_thought_oto=False,
        show_chain_of_thought_internal_group=True,
        show_chain_of_thought_cross_org_group=False,
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "s1",
    }
    assert effective_show_chain_of_thought(cfg, body) is True


def test_effective_cot_cross_org_prefers_cross_flag() -> None:
    cfg = SimpleNamespace(
        show_chain_of_thought_oto=True,
        show_chain_of_thought_internal_group=True,
        show_chain_of_thought_cross_org_group=False,
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "$:LWCP_v1:$cross-org-token",
    }
    assert effective_show_chain_of_thought(cfg, body) is False


def test_effective_cot_cross_org_when_enabled() -> None:
    cfg = SimpleNamespace(
        show_chain_of_thought_oto=False,
        show_chain_of_thought_internal_group=False,
        show_chain_of_thought_cross_org_group=True,
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "$:LWCP_v1:$cross-org-token",
    }
    assert effective_show_chain_of_thought(cfg, body) is True


def test_effective_cot_unknown_scope_returns_false() -> None:
    cfg = SimpleNamespace(
        show_chain_of_thought_oto=True,
        show_chain_of_thought_internal_group=True,
        show_chain_of_thought_cross_org_group=True,
    )
    assert effective_show_chain_of_thought(cfg, {}) is False
