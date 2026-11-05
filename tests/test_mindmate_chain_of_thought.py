"""MindMate replies follow the organization chain-of-thought switch."""

from types import SimpleNamespace

from services.mindmate.chain_of_thought import (
    MindmateThinkingGate,
    organization_shows_chain_of_thought,
)


def test_organization_switch_is_on_when_any_scope_is_enabled() -> None:
    """The editor writes one switch onto every scope flag."""
    hidden = SimpleNamespace(
        show_chain_of_thought_oto=False,
        show_chain_of_thought_internal_group=False,
        show_chain_of_thought_cross_org_group=False,
    )
    shown = SimpleNamespace(
        show_chain_of_thought_oto=True,
        show_chain_of_thought_internal_group=True,
        show_chain_of_thought_cross_org_group=True,
    )
    assert organization_shows_chain_of_thought(None) is False
    assert organization_shows_chain_of_thought(hidden) is False
    assert organization_shows_chain_of_thought(shown) is True


def test_gate_removes_thinking_tags_when_switch_is_off() -> None:
    """Hidden thinking never reaches the MindMate transcript."""
    gate = MindmateThinkingGate(False)
    visible = gate.visible_answer("Before <think>secret</think> after")
    gate.note_agent_thought({"thought": "native plan"})
    assert "secret" not in visible
    assert "after" in visible
    assert gate.closing_thinking_delta() == ""


def test_gate_keeps_thinking_and_native_thought_when_switch_is_on() -> None:
    """Shown thinking stays in the answer, and agent_thought is appended when tags are absent."""
    tagged = MindmateThinkingGate(True)
    visible = tagged.visible_answer("Before <thinking>secret</thinking> after")
    tagged.note_agent_thought({"thought": "native plan"})
    assert "secret" in visible
    assert tagged.closing_thinking_delta() == ""

    native_only = MindmateThinkingGate(True)
    assert native_only.visible_answer("Just the answer") == "Just the answer"
    native_only.note_agent_thought({"thought": "native plan"})
    assert native_only.closing_thinking_delta() == "<think>\nnative plan\n</think>\n"
