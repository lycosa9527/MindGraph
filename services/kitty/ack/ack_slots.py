"""Slot extraction for Kitty acknowledgment templates."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.diagram.mindmap_identity import is_machine_node_id
from services.kitty.ack.ack_action_resolve import last_user_utterance


def enrich_ack_session_context(
    session_context: Optional[Dict[str, Any]],
    voice_session: Optional[Dict[str, Any]] = None,
    *,
    diagram_type: str = "",
    command_text: str = "",
) -> Dict[str, Any]:
    """Merge voice-session fields needed for acknowledgment templates."""
    merged: Dict[str, Any] = dict(session_context) if isinstance(session_context, dict) else {}
    if isinstance(voice_session, dict):
        history = voice_session.get("conversation_history")
        if isinstance(history, list):
            merged["conversation_history"] = history
        session_type = voice_session.get("diagram_type")
        if session_type and not merged.get("diagram_type"):
            merged["diagram_type"] = str(session_type)
    if diagram_type and not merged.get("diagram_type"):
        merged["diagram_type"] = diagram_type
    if command_text.strip() and not last_user_utterance(merged):
        merged["conversation_history"] = [{"role": "user", "content": command_text.strip()}]
    return merged


_DELETE_PREFIXES = (
    "请帮我删除",
    "帮我删除",
    "请删除",
    "删除",
    "删掉",
    "去掉",
    "移除",
)
_DELETE_SUFFIXES = (
    "这个分支。",
    "这个分支",
    "这个节点。",
    "这个节点",
    "分支。",
    "分支",
    "节点。",
    "节点",
    "。",
    "！",
)


def _label_from_delete_utterance(utterance: str) -> str:
    """Pull a spoken node label out of a delete sentence when slots have no target."""
    text = utterance.strip()
    matched_prefix = False
    for prefix in _DELETE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            matched_prefix = True
            break
    if not matched_prefix:
        return ""
    text = text.strip("「」『』\"'")
    for suffix in _DELETE_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    text = text.strip("「」『』\"'")
    if not text or is_machine_node_id(text):
        return ""
    return _clip_label(text)


def _clip_label(value: Any, *, limit: int = 48) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _branch_label_from_session(
    session_context: Optional[Dict[str, Any]],
    branch_index: int,
) -> str:
    if not isinstance(session_context, dict):
        return ""
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        return ""
    children = diagram_data.get("children")
    if not isinstance(children, list) or branch_index < 0 or branch_index >= len(children):
        return ""
    branch = children[branch_index]
    if not isinstance(branch, dict):
        return ""
    for key in ("text", "label", "name"):
        raw = branch.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _node_label_from_session(
    session_context: Optional[Dict[str, Any]],
    hint: str,
) -> str:
    if not isinstance(session_context, dict) or not hint:
        return ""
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        return ""
    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if str(node.get("id") or "") != hint:
                continue
            for key in ("text", "label"):
                raw = node.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
            data = node.get("data")
            if isinstance(data, dict):
                label = data.get("label")
                if isinstance(label, str) and label.strip():
                    return label.strip()
    children = diagram_data.get("children")
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            if str(child.get("id") or "") != hint:
                continue
            for key in ("text", "label", "name"):
                raw = child.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
    return ""


def _display_slot(value: Any, session_context: Optional[Dict[str, Any]]) -> str:
    text = _clip_label(value)
    if not text:
        return ""
    if not is_machine_node_id(text):
        return text
    label = _node_label_from_session(session_context, text)
    return _clip_label(label) if label else ""


def slots_from_command(
    action: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Build template slots from a routed tool command."""
    slots: Dict[str, str] = {}

    target = command.get("target")
    if isinstance(target, str) and target.strip():
        display = _display_slot(target, session_context)
        if display:
            slots["target"] = display

    new_text = command.get("new_text")
    if isinstance(new_text, str) and new_text.strip():
        display = _display_slot(new_text, session_context)
        if display:
            slots["new_text"] = display
    elif "target" in slots and action in ("update_node", "update_center"):
        slots["new_text"] = slots["target"]

    ident = command.get("node_identifier")
    if isinstance(ident, str) and ident.strip():
        display = _display_slot(ident, session_context)
        if display:
            slots["old_text"] = display
    elif ident is not None and str(ident).strip():
        display = _display_slot(ident, session_context)
        if display:
            slots["old_text"] = display

    if "target" not in slots:
        node_id = command.get("node_id")
        if isinstance(node_id, str) and node_id.strip():
            display = _display_slot(node_id, session_context)
            if display:
                slots["target"] = display
    if action == "delete_node" and "target" not in slots:
        if slots.get("old_text"):
            slots["target"] = slots["old_text"]
        else:
            from_utterance = _label_from_delete_utterance(last_user_utterance(session_context))
            if from_utterance:
                slots["target"] = from_utterance

    branch_index_raw = command.get("branch_index")
    if branch_index_raw is not None:
        try:
            branch_index = int(branch_index_raw)
            branch_label = _branch_label_from_session(session_context, branch_index)
            if branch_label:
                slots["branch_label"] = _clip_label(branch_label)
        except (TypeError, ValueError):
            pass

    for key in ("left", "right", "title", "event", "whole", "dimension"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            slots[key] = _clip_label(raw)

    return slots


def slots_from_diagram_update(action: str, updates: Any) -> Dict[str, str]:
    """Build template slots from a diagram_update WS payload."""
    slots: Dict[str, str] = {}
    act = str(action or "").strip()

    if act == "update_center" and isinstance(updates, dict):
        for key in ("new_text", "title", "event", "whole", "dimension", "left", "right"):
            raw = updates.get(key)
            if isinstance(raw, str) and raw.strip():
                slots["new_text"] = _clip_label(raw)
                if key in ("left", "right"):
                    slots[key] = _clip_label(raw)
                break
        return slots

    if act in ("update_nodes", "add_nodes", "remove_nodes") and isinstance(updates, list):
        first = updates[0] if updates else None
        if isinstance(first, dict):
            new_text = first.get("new_text") or first.get("text")
            if isinstance(new_text, str) and new_text.strip():
                slots["new_text"] = _clip_label(new_text)
                slots["target"] = slots["new_text"]
            node_id = first.get("node_id")
            if isinstance(node_id, str) and node_id.strip():
                slots["node_id"] = _clip_label(node_id)
        return slots

    if isinstance(updates, dict):
        for key in ("text", "new_text", "target", "label", "topic"):
            raw = updates.get(key)
            if isinstance(raw, str) and raw.strip():
                slots["target"] = _clip_label(raw)
                slots["new_text"] = slots["target"]
                break

    return slots


def echo_hint_from_slots(slots: Dict[str, str], *, lang: str) -> str:
    """Short phrase for low-confidence clarify templates."""
    if slots.get("old_text") and slots.get("new_text"):
        if lang == "en":
            return f'change "{slots["old_text"]}" to "{slots["new_text"]}"'
        return f"把「{slots['old_text']}」改为「{slots['new_text']}」"
    if slots.get("branch_label") and slots.get("target"):
        if lang == "en":
            return f'add "{slots["target"]}" under "{slots["branch_label"]}"'
        return f"在「{slots['branch_label']}」下添加「{slots['target']}」"
    if slots.get("target"):
        if lang == "en":
            return f'work on "{slots["target"]}"'
        return f"处理「{slots['target']}」"
    if slots.get("new_text"):
        if lang == "en":
            return f'update to "{slots["new_text"]}"'
        return f"改成「{slots['new_text']}」"
    return ""
