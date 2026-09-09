"""Default clarify menu when Kitty cannot safely edit.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.kitty.routing.diagram_agent_context import resolve_diagram_node_ref

PENDING_INTENT_SLOT_KEY = "_pending_intent_slot"
_CANCEL_TEXTS = frozenset(
    {
        "取消",
        "算了",
        "不用",
        "不用了",
        "先不了",
        "cancel",
        "never mind",
        "nevermind",
    }
)


def _diagram_data(session_context: Dict[str, Any]) -> Dict[str, Any]:
    raw = session_context.get("diagram_data")
    return raw if isinstance(raw, dict) else {}


def _selected_focus(session_context: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Return (node_id, label) for the current canvas selection."""
    selected_raw = session_context.get("selected_nodes")
    diagram = _diagram_data(session_context)
    if not isinstance(selected_raw, list):
        selected_raw = diagram.get("selected_nodes")
    if not isinstance(selected_raw, list):
        return None
    for raw in selected_raw:
        if not isinstance(raw, str) or not raw.strip():
            continue
        resolved = resolve_diagram_node_ref(diagram, node_id=raw.strip())
        if not resolved:
            continue
        node_id = resolved.get("node_id")
        label = resolved.get("node_label") or node_id
        if isinstance(node_id, str) and node_id.strip() and node_id != "topic":
            return node_id.strip(), (label.strip() if isinstance(label, str) and label.strip() else node_id)
    return None


def _option(
    label: str,
    action: str,
    *,
    target: str = "",
    node_id: str = "",
    followup: str = "",
    slot_action: str = "",
    new_text: str = "",
) -> Dict[str, Any]:
    cmd: Dict[str, Any] = {"action": action, "confidence": 0.9}
    if target:
        cmd["target"] = target
    if node_id:
        cmd["node_id"] = node_id
    if followup:
        cmd["followup"] = followup
    if slot_action:
        cmd["slot_action"] = slot_action
    if new_text:
        cmd["new_text"] = new_text
    return {"label": label, "command": cmd}


def default_intent_clarify_command(
    *,
    lang: str,
    session_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Short next-step menu for greetings and vague edits."""
    use_en = lang == "en"
    focus = _selected_focus(session_context)
    if focus is not None:
        node_id, label = focus
        question = f'What should I do with "{label}"?' if use_en else f"「{label}」想怎么改？"
        rows = [
            _option(
                f'Rename "{label}"' if use_en else "改名称",
                "ask_followup",
                node_id=node_id,
                slot_action="update_node",
                followup="What is the new name?" if use_en else "想改成什么名称？",
            ),
            _option(
                f'Delete "{label}"' if use_en else "删除",
                "delete_node",
                target=label,
                node_id=node_id,
            ),
            _option(
                "Fill this branch" if use_en else "补全这个分支",
                "auto_complete_branch",
                target=label,
                node_id=node_id,
            ),
        ]
    else:
        question = "How should I change this map?" if use_en else "想怎么改这张图？"
        rows = [
            _option(
                "Change the topic" if use_en else "改主题",
                "ask_followup",
                slot_action="update_center",
                followup="What should the topic be?" if use_en else "主题想改成什么？",
            ),
            _option(
                "Add a branch" if use_en else "添加分支",
                "ask_followup",
                slot_action="add_node",
                followup="What branch should I add?" if use_en else "要添加哪条分支？",
            ),
            _option(
                "Auto-complete the map" if use_en else "自动补全这张图",
                "auto_complete",
            ),
        ]
    labels = [str(row["label"]) for row in rows]
    commands = [dict(row["command"]) for row in rows]
    return {
        "action": "clarify_options",
        "confidence": 0.9,
        "question": question,
        "options": labels,
        "option_commands": commands,
    }


def is_intent_slot_cancel(text: str) -> bool:
    """True when the user backs out of a follow-up slot."""
    return " ".join(text.strip().lower().split()) in _CANCEL_TEXTS


def arm_pending_intent_slot(
    session: Optional[Dict[str, Any]],
    command: Dict[str, Any],
) -> bool:
    """Remember the next utterance fills ``slot_action`` (rename / add / topic)."""
    if not isinstance(session, dict):
        return False
    slot_action = command.get("slot_action")
    action = slot_action.strip() if isinstance(slot_action, str) else ""
    if action not in {"update_center", "add_node", "update_node"}:
        return False
    slot: Dict[str, Any] = {"action": action}
    node_id = command.get("node_id")
    if isinstance(node_id, str) and node_id.strip():
        slot["node_id"] = node_id.strip()
    followup = command.get("followup")
    if isinstance(followup, str) and followup.strip():
        slot["followup"] = followup.strip()
    session[PENDING_INTENT_SLOT_KEY] = slot
    return True


def clear_pending_intent_slot(session: Optional[Dict[str, Any]]) -> None:
    """Drop a follow-up slot."""
    if isinstance(session, dict):
        session.pop(PENDING_INTENT_SLOT_KEY, None)


def consume_pending_intent_slot(
    session: Optional[Dict[str, Any]],
    text: str,
) -> Optional[Dict[str, Any]]:
    """Turn the next user line into the armed edit, or None."""
    if not isinstance(session, dict):
        return None
    raw = session.get(PENDING_INTENT_SLOT_KEY)
    if not isinstance(raw, dict):
        return None
    filled = text.strip()
    if not filled or is_intent_slot_cancel(filled):
        session.pop(PENDING_INTENT_SLOT_KEY, None)
        return None
    action = str(raw.get("action") or "").strip()
    if action not in {"update_center", "add_node", "update_node"}:
        session.pop(PENDING_INTENT_SLOT_KEY, None)
        return None
    session.pop(PENDING_INTENT_SLOT_KEY, None)
    command: Dict[str, Any] = {"action": action, "confidence": 0.9, "target": filled}
    if action == "update_node":
        command["new_text"] = filled
    node_id = raw.get("node_id")
    if isinstance(node_id, str) and node_id.strip():
        command["node_id"] = node_id.strip()
    return command


def ask_followup_text(command: Dict[str, Any], *, lang: str) -> str:
    """User-facing prompt after they pick a suggestion that needs a value."""
    followup = command.get("followup")
    if isinstance(followup, str) and followup.strip():
        return followup.strip()
    return "What should it be?" if lang == "en" else "请再说具体一点。"


def default_clarify_labels(command: Dict[str, Any]) -> List[str]:
    """Labels for WS clarify chips."""
    raw = command.get("options")
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]
