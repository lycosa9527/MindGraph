"""User-referent grounding for Kitty canvas mutations.

A tool may change only objects the user pointed at: a named label, an armed
clarify/follow-up pick, or a deictic plus the current selection. The model
cannot authorize a target by picking an id from the snapshot.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.kitty.routing.diagram_agent_context import resolve_diagram_node_ref

UNGROUNDED_ERROR = "ungrounded_target"

NODE_SCOPED_ACTIONS = frozenset(
    {
        "delete_node",
        "update_node",
        "auto_complete_branch",
        "select_node",
    }
)
CENTER_ACTIONS = frozenset({"update_center"})
MAP_ACTIONS = frozenset({"auto_complete"})
ADD_ACTIONS = frozenset({"add_node"})
GROUNDED_ACTIONS = NODE_SCOPED_ACTIONS | CENTER_ACTIONS | MAP_ACTIONS | ADD_ACTIONS
CLARIFY_SOURCES = frozenset({"clarify_pick", "ask_followup"})

_DEICTIC_RE = re.compile(
    r"这个|那个|此项|该节点|\bthis(?:\s+one)?\b|\bthat(?:\s+one)?\b",
    re.IGNORECASE,
)
_FILL_VERB_RE = re.compile(
    r"(?:自动)?(?:补全|补完|完善|填充)|auto[-\s]?complete",
    re.IGNORECASE,
)
_MAP_NOUN_RE = re.compile(
    r"整张|整幅|导图|图示|思维导图|mind\s*map|the\s+(?:whole\s+)?(?:diagram|map)",
    re.IGNORECASE,
)
_SHORT_PREFIX = frozenset("把将删掉除补改「『\"'向对")
_SHORT_SUFFIX = frozenset("这个条分支」』改换成")
_TOPIC_KEYS = frozenset({"topic", "center"})


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    """Whether a mapped command may run, and why."""

    allowed: bool
    reason: str
    node_id: str = ""
    label: str = ""


def _diagram_data(session_context: Dict[str, Any]) -> Dict[str, Any]:
    raw = session_context.get("diagram_data")
    return raw if isinstance(raw, dict) else {}


def _first_selected(session_context: Dict[str, Any]) -> Optional[Dict[str, str]]:
    diagram = _diagram_data(session_context)
    selected_raw = session_context.get("selected_nodes")
    if not isinstance(selected_raw, list):
        selected_raw = diagram.get("selected_nodes")
    if not isinstance(selected_raw, list):
        return None
    for raw in selected_raw:
        if not isinstance(raw, str) or not raw.strip():
            continue
        resolved = resolve_diagram_node_ref(diagram, node_id=raw.strip())
        if resolved:
            return resolved
    return None


def _command_label(command: Dict[str, Any]) -> str:
    for key in ("node_label", "node_identifier", "target", "text"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _new_text(command: Dict[str, Any]) -> str:
    raw = command.get("new_text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    target = command.get("target")
    if isinstance(target, str) and target.strip():
        return target.strip()
    return ""


def _is_latin_token(label: str) -> bool:
    return all(ord(char) < 128 and (char.isalnum() or char in "-_'") for char in label)


def _is_cjk_ideograph(char: str) -> bool:
    return bool(char) and 0x4E00 <= ord(char) <= 0x9FFF


def _short_cjk_delimited(utterance: str, label: str) -> bool:
    start = 0
    while True:
        index = utterance.find(label, start)
        if index < 0:
            return False
        prev_char = utterance[index - 1] if index else ""
        next_char = utterance[index + len(label)] if index + len(label) < len(utterance) else ""
        isolated = (not _is_cjk_ideograph(prev_char)) and (not _is_cjk_ideograph(next_char))
        marked = prev_char in _SHORT_PREFIX or next_char in _SHORT_SUFFIX
        if isolated or marked:
            return True
        start = index + 1


def label_mentioned(utterance: str, label: str) -> bool:
    """True when the user text names this canvas label."""
    text = utterance.strip()
    needle = label.strip()
    if not text or not needle or needle not in text:
        return False
    if _is_latin_token(needle):
        if re.search(rf"\b{re.escape(needle)}\b", text, flags=re.IGNORECASE):
            return True
        index = text.lower().find(needle.lower())
        if index < 0:
            return False
        prev_char = text[index - 1] if index else ""
        next_char = text[index + len(needle)] if index + len(needle) < len(text) else ""
        return (not prev_char.isascii() or not prev_char.isalnum()) and (
            not next_char.isascii() or not next_char.isalnum()
        )
    if len(needle) >= 2:
        return True
    return _short_cjk_delimited(text, needle)


def _has_deictic(utterance: str) -> bool:
    return _DEICTIC_RE.search(utterance) is not None


def _named_existing_branch(utterance: str, session_context: Dict[str, Any]) -> bool:
    nodes_raw = _diagram_data(session_context).get("nodes")
    typed = [node for node in nodes_raw if isinstance(node, dict)] if isinstance(nodes_raw, list) else []
    for node in typed:
        node_id = node.get("id")
        if node_id in _TOPIC_KEYS:
            continue
        text = node.get("text")
        if isinstance(text, str) and len(text.strip()) >= 2 and label_mentioned(utterance, text.strip()):
            return True
    return False


def _deny(reason: str) -> GroundingDecision:
    return GroundingDecision(allowed=False, reason=reason)


def _allow(reason: str, *, node_id: str = "", label: str = "") -> GroundingDecision:
    return GroundingDecision(allowed=True, reason=reason, node_id=node_id, label=label)


def _resolve_command_node(
    command: Dict[str, Any],
    session_context: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    diagram = _diagram_data(session_context)
    node_id = command.get("node_id")
    if isinstance(node_id, str) and node_id.strip():
        resolved = resolve_diagram_node_ref(diagram, node_id=node_id.strip())
        if resolved:
            return resolved
    label = _command_label(command)
    if label:
        return resolve_diagram_node_ref(diagram, label=label)
    return None


def _bind_node(command: Dict[str, Any], resolved: Dict[str, str]) -> None:
    node_id = resolved.get("node_id")
    label = resolved.get("node_label")
    if isinstance(node_id, str) and node_id.strip():
        command["node_id"] = node_id.strip()
    if isinstance(label, str) and label.strip():
        if not command.get("target") or command.get("action") != "update_node":
            command.setdefault("target", label.strip())


def _parent_grounded(command: Dict[str, Any], utterance: str, session_context: Dict[str, Any]) -> bool:
    parent = command.get("parent_ref") or command.get("parent_node_id")
    if not isinstance(parent, str) or not parent.strip():
        return True
    token = parent.strip()
    if token in _TOPIC_KEYS:
        return True
    if label_mentioned(utterance, token):
        return True
    resolved = resolve_diagram_node_ref(_diagram_data(session_context), node_id=token)
    if resolved is None:
        resolved = resolve_diagram_node_ref(_diagram_data(session_context), label=token)
    if resolved is None:
        return False
    parent_label = resolved.get("node_label") or ""
    return bool(parent_label) and label_mentioned(utterance, parent_label)


def _ground_add(command: Dict[str, Any], utterance: str, session_context: Dict[str, Any]) -> GroundingDecision:
    label = _command_label(command)
    if not label or not label_mentioned(utterance, label):
        return _deny(UNGROUNDED_ERROR)
    if not _parent_grounded(command, utterance, session_context):
        return _deny(UNGROUNDED_ERROR)
    return _allow("grounded_add", label=label)


def _ground_center(command: Dict[str, Any], utterance: str) -> GroundingDecision:
    new_text = _new_text(command)
    if new_text and label_mentioned(utterance, new_text):
        return _allow("grounded_center", label=new_text)
    return _deny(UNGROUNDED_ERROR)


def _ground_map(utterance: str, session_context: Dict[str, Any]) -> GroundingDecision:
    if not _FILL_VERB_RE.search(utterance) and not _MAP_NOUN_RE.search(utterance):
        return _deny(UNGROUNDED_ERROR)
    if _named_existing_branch(utterance, session_context) and not _MAP_NOUN_RE.search(utterance):
        return _deny(UNGROUNDED_ERROR)
    return _allow("grounded_map")


def _ground_node(
    command: Dict[str, Any],
    utterance: str,
    session_context: Dict[str, Any],
    *,
    source: str,
) -> GroundingDecision:
    resolved = _resolve_command_node(command, session_context)
    selected = _first_selected(session_context)
    if source in CLARIFY_SOURCES:
        if resolved is None:
            return _deny(UNGROUNDED_ERROR)
        _bind_node(command, resolved)
        return _allow(
            "grounded_clarify",
            node_id=resolved["node_id"],
            label=resolved.get("node_label") or "",
        )

    if resolved is not None:
        label = resolved.get("node_label") or ""
        if label and label_mentioned(utterance, label):
            if command.get("action") == "update_node":
                new_text = _new_text(command)
                if new_text and new_text != label and not label_mentioned(utterance, new_text):
                    return _deny(UNGROUNDED_ERROR)
            _bind_node(command, resolved)
            return _allow(
                "grounded_mention",
                node_id=resolved.get("node_id") or "",
                label=label,
            )

    if _has_deictic(utterance) and selected:
        if resolved and resolved.get("node_id") != selected.get("node_id"):
            return _deny(UNGROUNDED_ERROR)
        if command.get("action") == "update_node":
            new_text = _new_text(command)
            selected_label = selected.get("node_label") or ""
            if not new_text or new_text == selected_label or not label_mentioned(utterance, new_text):
                return _deny(UNGROUNDED_ERROR)
        _bind_node(command, selected)
        return _allow(
            "grounded_deictic",
            node_id=selected.get("node_id") or "",
            label=selected.get("node_label") or "",
        )

    return _deny(UNGROUNDED_ERROR)


def apply_command_grounding(
    command: Dict[str, Any],
    *,
    user_text: str,
    session_context: Dict[str, Any],
    source: str = "",
) -> GroundingDecision:
    """Allow or reject a mapped command. May attach ``node_id`` when deictic."""
    action = str(command.get("action") or "").strip()
    if action not in GROUNDED_ACTIONS:
        return _allow("not_required")
    utterance = user_text.strip()
    if not utterance:
        return _deny(UNGROUNDED_ERROR)
    if action in ADD_ACTIONS:
        return _ground_add(command, utterance, session_context)
    if action in CENTER_ACTIONS:
        return _ground_center(command, utterance)
    if action in MAP_ACTIONS:
        return _ground_map(utterance, session_context)
    return _ground_node(command, utterance, session_context, source=source)
