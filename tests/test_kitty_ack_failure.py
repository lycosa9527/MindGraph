"""Tests for action- and code-aware Kitty failure acknowledgments."""

from __future__ import annotations

from services.kitty.ack.ack_failure import (
    render_failure_ack_for_command,
    resolve_failure_ack_key,
)


def test_add_branch_failure_mentions_target() -> None:
    """Failure ack for add_node includes branch target and apology."""
    command = {"action": "add_node", "target": "中国"}
    session = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "增加一个中国的分支"}],
    }
    text = render_failure_ack_for_command(
        "add_node",
        command,
        session,
        error_code="verify_failed",
        lang="zh",
    )
    assert "中国" in text
    assert "分支" in text
    assert "抱歉" in text


def test_update_node_failure_mentions_old_and_new() -> None:
    """Failure ack for update_node mentions prior and new labels."""
    command = {
        "action": "update_node",
        "node_identifier": "食",
        "target": "小吃",
    }
    text = render_failure_ack_for_command(
        "update_node",
        command,
        {},
        error_code="apply_noop",
        lang="zh",
    )
    assert "食" in text
    assert "小吃" in text


def test_busy_llm_code_overrides_action_variant() -> None:
    """busy_llm_generating maps to the busy-llm failure template."""
    command = {"action": "add_node", "target": "中国"}
    session = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "增加一个中国的分支"}],
    }
    key = resolve_failure_ack_key(
        "add_node",
        command,
        session,
        {"target": "中国"},
        error_code="busy_llm_generating",
    )
    assert key == "diagram.failed.busy_llm"
    text = render_failure_ack_for_command(
        "add_node",
        command,
        session,
        error_code="busy_llm_generating",
        lang="zh",
    )
    assert "自动执行" in text or "streaming" in text.lower()


def test_delete_branch_failure() -> None:
    """Failure ack for delete_node mentions the branch label."""
    command = {"action": "delete_node", "target": "历史"}
    session = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "删除历史分支"}],
    }
    text = render_failure_ack_for_command(
        "delete_node",
        command,
        session,
        lang="zh",
    )
    assert "历史" in text
    assert "分支" in text


def test_persist_failure_code() -> None:
    """hub_persist_failed ack mentions sync failure."""
    text = render_failure_ack_for_command(
        "update_center",
        {"action": "update_center", "target": "宜家"},
        {},
        error_code="hub_persist_failed",
        lang="zh",
    )
    assert "同步" in text
