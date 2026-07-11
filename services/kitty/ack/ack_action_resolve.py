"""Action-variant resolution for Kitty node-operation acknowledgments."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

AddNodeVariant = Literal["branch", "child", "plain"]
DeleteNodeVariant = Literal["branch", "child", "plain"]
AckPhase = Literal["progress", "done"]


def _is_mindmap(session_context: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(session_context, dict):
        return False
    diagram_type = str(session_context.get("diagram_type") or "").strip()
    return diagram_type in ("mindmap", "mind_map")


def last_user_utterance(session_context: Optional[Dict[str, Any]]) -> str:
    """Return the most recent user message from session conversation history."""
    if not isinstance(session_context, dict):
        return ""
    history = session_context.get("conversation_history")
    if not isinstance(history, list):
        return ""
    for turn in reversed(history):
        if not isinstance(turn, dict):
            continue
        if turn.get("role") != "user":
            continue
        content = turn.get("content")
        if isinstance(content, str):
            return content.strip()
    return ""


def utterance_mentions_branch(utterance: str) -> bool:
    """True when the user text refers to a main branch."""
    if "分支" in utterance:
        return True
    return "branch" in utterance.lower()


def utterance_mentions_child(utterance: str) -> bool:
    """True when the user text refers to a child/sub-item node."""
    child_markers = ("子节点", "子项", "子分支", "下级")
    if any(marker in utterance for marker in child_markers):
        return True
    lower = utterance.lower()
    return "child" in lower or "sub-node" in lower or "subnode" in lower


def classify_add_node_variant(
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
) -> AddNodeVariant:
    """Classify add_node into branch, child, or plain node add."""
    if not _is_mindmap(session_context):
        return "plain"
    branch_index = command.get("branch_index")
    child_index = command.get("child_index")
    if branch_index is not None and child_index is not None:
        return "child"
    if command.get("node_index") is not None:
        return "plain"
    target = command.get("target")
    if not isinstance(target, str) or not target.strip():
        return "plain"
    utterance = last_user_utterance(session_context)
    if utterance_mentions_branch(utterance):
        return "branch"
    if utterance_mentions_child(utterance):
        return "child"
    if branch_index is None and child_index is None:
        return "branch"
    return "plain"


def classify_delete_node_variant(
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
) -> DeleteNodeVariant:
    """Classify delete_node into branch, child, or plain node delete."""
    if not _is_mindmap(session_context):
        return "plain"
    branch_index = command.get("branch_index")
    child_index = command.get("child_index")
    if branch_index is not None and child_index is not None:
        return "child"
    target = command.get("target")
    if not isinstance(target, str) or not target.strip():
        return "plain"
    utterance = last_user_utterance(session_context)
    if utterance_mentions_branch(utterance):
        return "branch"
    return "plain"


def resolve_update_node_ack_key(slots: Dict[str, str], *, phase: AckPhase) -> str:
    """Pick update_node template key for progress or done phase."""
    has_old = bool(slots.get("old_text") and slots.get("new_text"))
    if phase == "done":
        return "diagram.update_node.done" if has_old else "diagram.update_node.done_no_old"
    return "diagram.update_node.progress" if has_old else "diagram.update_node.progress_no_old"


def resolve_update_center_ack_key(slots: Dict[str, str], *, phase: AckPhase) -> str:
    """Pick update_center template key for progress or done phase."""
    if slots.get("left") and slots.get("right"):
        suffix = "double_bubble"
        return f"diagram.update_center.{suffix}.done" if phase == "done" else f"diagram.update_center.{suffix}.progress"
    return "diagram.update_center.done" if phase == "done" else "diagram.update_center.progress"


def resolve_add_node_ack_key(
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
    slots: Dict[str, str],
    *,
    phase: AckPhase,
) -> str:
    """Pick add_node template key based on diagram-specific add variant."""
    variant = classify_add_node_variant(command, session_context)
    done = phase == "done"
    if variant == "branch":
        return "diagram.add_branch.done" if done else "diagram.add_branch.progress"
    if variant == "child":
        if slots.get("branch_label"):
            return "diagram.add_child.branch.done" if done else "diagram.add_child.branch.progress"
        return "diagram.add_child.done" if done else "diagram.add_child.progress"
    return "diagram.add_node.done" if done else "diagram.add_node.progress"


def resolve_delete_node_ack_key(
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
    slots: Dict[str, str],
    *,
    phase: AckPhase,
) -> str:
    """Pick delete_node template key based on diagram-specific delete variant."""
    variant = classify_delete_node_variant(command, session_context)
    done = phase == "done"
    if variant == "branch":
        return "diagram.delete_branch.done" if done else "diagram.delete_branch.progress"
    if variant == "child":
        if slots.get("branch_label"):
            return "diagram.delete_child.branch.done" if done else "diagram.delete_child.branch.progress"
        if slots.get("target"):
            return "diagram.delete_child.target.done" if done else "diagram.delete_child.target.progress"
        return "diagram.delete_child.done" if done else "diagram.delete_child.progress"
    return "diagram.delete_node.done" if done else "diagram.delete_node.progress"
