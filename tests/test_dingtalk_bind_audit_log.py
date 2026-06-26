"""Tests for DingTalk bind and MindBot admin-tool audit logging."""

from __future__ import annotations

import logging

from services.auth.dingtalk_bind_audit_log import log_claim_ok, log_web_mint_started
from services.mindbot.tools.audit_log import log_tool_intercepted, log_tool_outcome


def test_mindbot_tool_audit_prefix(caplog) -> None:
    """Admin-tool logs use [MindBotTool] prefix and skip_dify marker."""
    caplog.set_level(logging.INFO)
    log_tool_intercepted(tool="pair_code", org_id=5, staff_id="staffA", pipeline_ctx="ctx=1")
    assert "[MindBotTool]" in caplog.text
    assert "skip_dify=1" in caplog.text
    assert "tool=pair_code" in caplog.text


def test_mindbot_tool_outcome_includes_user_id(caplog) -> None:
    """Tool outcome logs include resolved MindGraph user id when known."""
    caplog.set_level(logging.INFO)
    log_tool_outcome(
        tool="pair_code",
        org_id=5,
        staff_id="staffA",
        purpose="bind",
        outcome="bind_ok",
        ok=True,
        user_id=42,
        pipeline_ctx="ctx=2",
    )
    assert "user_id=42" in caplog.text
    assert "ok=1" in caplog.text


def test_dingtalk_bind_web_audit_prefix(caplog) -> None:
    """Web mint logs use [DingtalkBind:web] prefix."""
    caplog.set_level(logging.INFO)
    log_web_mint_started(user_id=42, org_id=5, purpose="bind")
    assert "[DingtalkBind:web]" in caplog.text
    assert "mint_started" in caplog.text


def test_dingtalk_bind_claim_audit_prefix(caplog) -> None:
    """Claim logs use [DingtalkBind:claim] prefix."""
    caplog.set_level(logging.INFO)
    log_claim_ok(action="bind", user_id=42, org_id=5, staff_id="staffA")
    assert "[DingtalkBind:claim]" in caplog.text
    assert "action=bind" in caplog.text
