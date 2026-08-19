"""Tool-result message contract for the typed Kitty agent loop."""

from __future__ import annotations

from services.diagram_edit.types import ToolResult, VerificationReport
from services.kitty.agent_loop.messages import (
    append_assistant_tool_calls,
    append_tool_message,
    extract_tool_calls,
)
from services.kitty.agent_loop.results import (
    created_node_ids_from_payload,
    encode_tool_content,
    is_retryable_error,
    summarize_payload_for_memory,
    tool_result_content,
)
from services.kitty.session.memory import KittySessionMemory


def test_tool_result_content_is_to_dict() -> None:
    """Structural tool rows store ToolResult.to_dict() verbatim."""
    result = ToolResult(
        status="applied",
        mutation_id="mut-applied",
        revision=4,
        applied_ops=[{"op": "add_node", "node_id": "uid-new", "text": "历史"}],
        verification=VerificationReport(ok=True, checks=["node_exists"]),
    )
    payload = tool_result_content(result)
    assert payload == result.to_dict()
    assert payload["status"] == "applied"
    assert payload["revision"] == 4
    assert created_node_ids_from_payload(payload) == ["uid-new"]


def test_append_tool_message_applied() -> None:
    """role=tool row carries tool_call_id and applied JSON."""
    result = ToolResult(
        status="applied",
        mutation_id="mut-applied",
        revision=2,
        applied_ops=[{"op": "update_node", "node_id": "uid-hist"}],
    )
    messages: list[dict] = []
    append_tool_message(messages, tool_call_id="call_applied", payload=tool_result_content(result))
    assert messages[0]["role"] == "tool"
    assert messages[0]["tool_call_id"] == "call_applied"
    assert messages[0]["content"] == encode_tool_content(result.to_dict())


def test_append_tool_message_verify_failed() -> None:
    """verify_failed is retryable and visible on the next chat_raw transcript."""
    result = ToolResult(
        status="failed",
        mutation_id="mut-vf",
        revision=3,
        error_code="verify_failed",
        message="canvas did not confirm node id",
    )
    messages: list[dict] = []
    append_tool_message(messages, tool_call_id="call_vf", payload=tool_result_content(result))
    assert is_retryable_error("verify_failed") is True
    assert '"error_code": "verify_failed"' in messages[0]["content"]
    assert messages[0]["tool_call_id"] == "call_vf"


def test_append_tool_message_stale_revision() -> None:
    """stale_revision is retryable observation JSON, not a user message."""
    result = ToolResult(
        status="failed",
        mutation_id="mut-stale",
        revision=1,
        error_code="stale_revision",
    )
    messages: list[dict] = []
    append_assistant_tool_calls(
        messages,
        [{"id": "call_stale", "name": "diagram.update_node", "arguments": "{}"}],
    )
    append_tool_message(messages, tool_call_id="call_stale", payload=tool_result_content(result))
    assert messages[0]["role"] == "assistant"
    assert messages[1]["role"] == "tool"
    assert messages[1]["tool_call_id"] == "call_stale"
    assert is_retryable_error("stale_revision") is True
    assert '"error_code": "stale_revision"' in messages[1]["content"]


def test_extract_tool_calls_normalizes_provider_shape() -> None:
    """Provider tool_calls become {id, name, arguments}."""
    calls = extract_tool_calls(
        {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "diagram.delete_node", "arguments": '{"node_id":"uid-a"}'},
                }
            ]
        }
    )
    assert calls == [{"id": "call_1", "name": "diagram.delete_node", "arguments": '{"node_id":"uid-a"}'}]


def test_memory_append_observation_stores_compact_summary() -> None:
    """Session memory stores a one-line tool observation."""
    memory = KittySessionMemory()
    payload = tool_result_content(
        ToolResult(
            status="applied",
            mutation_id="mut-1",
            revision=5,
            applied_ops=[{"op": "add_node", "node_id": "uid-created"}],
        )
    )
    memory.append_observation(
        summarize_payload_for_memory(payload, action="add_node"),
        action="add_node",
        revision=5,
    )
    turn = memory.recent_turns(1)[0]
    assert turn.source == "tool"
    assert turn.action_taken == "add_node"
    assert turn.diagram_revision == 5
    assert "applied" in turn.content
    assert "uid-created" in turn.content
