"""Tests for one-sentence command_detail activity tracking."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.one_sentence_command_detail import (
    build_one_sentence_command_detail,
    normalize_command_detail,
)
from services.kitty.session.one_sentence_turn_pg import turn_dict_to_row
from services.kitty.http.handlers import kitty_rest_one_sentence_diagram_activity
from models.domain.auth import User


def test_build_command_detail_includes_bus_ops() -> None:
    """command_detail embeds bus applied_ops and follow-up actions."""
    tool = SimpleNamespace(
        to_dict=lambda: {
            "status": "applied",
            "mutation_id": "mut-1",
            "revision": 4,
            "applied_ops": [{"op": "add_node", "text": "历史", "node_id": "n1"}],
        }
    )
    detail = build_one_sentence_command_detail(
        action="add_node",
        outcome="executed",
        command={
            "action": "add_node",
            "target": "历史",
            "confidence": 0.91,
            "follow_up_actions": [{"action": "auto_complete_branch"}],
        },
        tool_result=tool,
    )
    assert detail["action"] == "add_node"
    assert detail["command"]["target"] == "历史"
    assert detail["bus"]["mutation_id"] == "mut-1"
    assert detail["bus"]["applied_ops"][0]["node_id"] == "n1"
    assert detail["command"]["follow_up_actions"] == ["auto_complete_branch"]


def test_normalize_command_detail_rejects_non_dict() -> None:
    """Only dict payloads survive command_detail normalization."""
    assert normalize_command_detail("not-json") is None
    assert normalize_command_detail([]) is None
    assert normalize_command_detail({"action": "add_node"}) == {"action": "add_node"}


def test_turn_dict_to_row_keeps_command_detail() -> None:
    """PG row mapping preserves nested command_detail bus fields."""
    row = turn_dict_to_row(
        user_id=1,
        organization_id=2,
        scope="scope-1",
        session_id="sess-1",
        turn={
            "turn_id": "t1",
            "ts": 1_700_000_000,
            "role": "kitty",
            "content": "已添加历史",
            "phase": "edit",
            "source": "ack",
            "action": "add_node",
            "outcome": "executed",
            "request_id": "req-1",
            "command_detail": {
                "action": "add_node",
                "bus": {"mutation_id": "m1", "applied_ops": [{"op": "add_node", "node_id": "n9"}]},
            },
        },
    )
    assert row.action == "add_node"
    assert row.request_id == "req-1"
    assert row.command_detail is not None
    assert row.command_detail["bus"]["mutation_id"] == "m1"


@pytest.mark.asyncio
async def test_diagram_activity_handler_shapes_events() -> None:
    """REST diagram activity endpoint shapes node-action events."""
    user = MagicMock(spec=User)
    user.id = 7
    user.organization_id = 3

    with (
        patch(
            "services.kitty.http.handlers.kitty_http_allowed",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.user_may_access_kitty_scope",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.http.handlers.normalize_kitty_diagram_session_id",
            return_value="11111111-1111-1111-1111-111111111111",
        ),
        patch(
            "services.kitty.http.handlers.list_one_sentence_diagram_activity_pg",
            new=AsyncMock(
                return_value=[
                    {
                        "turn_id": "t1",
                        "ts": 10,
                        "role": "kitty",
                        "content": "已添加",
                        "phase": "edit",
                        "source": "ack",
                        "action": "add_node",
                        "outcome": "executed",
                        "user_text": "添加历史分支",
                        "request_id": "req-1",
                        "command_detail": {
                            "action": "add_node",
                            "command": {"target": "历史", "node_id": "n1"},
                            "bus": {
                                "mutation_id": "mut-9",
                                "applied_ops": [{"op": "add_node", "node_id": "n1"}],
                            },
                        },
                    }
                ]
            ),
        ),
    ):
        payload = await kitty_rest_one_sentence_diagram_activity(
            user,
            "11111111-1111-1111-1111-111111111111",
            limit=50,
            actions_only=True,
        )

    assert payload["ok"] is True
    assert payload["count"] == 1
    event = payload["events"][0]
    assert event["action"] == "add_node"
    assert event["node_id"] == "n1"
    assert event["mutation_id"] == "mut-9"
    assert event["user_text"] == "添加历史分支"
