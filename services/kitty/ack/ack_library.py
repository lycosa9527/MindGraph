"""Centralized Kitty acknowledgment template registry (zh/en)."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from services.kitty.ack.ack_action_resolve import (
    resolve_add_node_ack_key,
    resolve_delete_node_ack_key,
    resolve_update_center_ack_key,
    resolve_update_node_ack_key,
)
from services.kitty.ack.ack_slots import (
    echo_hint_from_slots,
    slots_from_command,
    slots_from_diagram_update,
)
from services.kitty.infra.bootstrap.kitty_unsupported_diagram_types import UnsupportedDiagramMatch

KittyLanguage = Literal["zh", "en"]

UnsupportedAckMatch = Union[UnsupportedDiagramMatch, Dict[str, str]]

_ACK_TEMPLATES: Dict[str, Dict[KittyLanguage, str]] = {
    "diagram.update_node.progress": {
        "zh": "好的，正在把「{old_text}」改为「{new_text}」…",
        "en": 'OK — changing "{old_text}" to "{new_text}"…',
    },
    "diagram.update_node.progress_no_old": {
        "zh": "好的，正在把节点改为「{new_text}」…",
        "en": 'OK — updating the node to "{new_text}"…',
    },
    "diagram.update_node.done": {
        "zh": "已将「{old_text}」改为「{new_text}」。",
        "en": 'Changed "{old_text}" to "{new_text}".',
    },
    "diagram.update_node.done_no_old": {
        "zh": "节点已更新为「{new_text}」。",
        "en": 'Node updated to "{new_text}".',
    },
    "diagram.update_center.progress": {
        "zh": "好的，正在把主题更新为「{new_text}」…",
        "en": 'OK — updating the topic to "{new_text}"…',
    },
    "diagram.update_center.done": {
        "zh": "主题已更新为「{new_text}」。",
        "en": 'Topic updated to "{new_text}".',
    },
    "diagram.update_center.double_bubble.progress": {
        "zh": "好的，正在更新为「{left}」和「{right}」…",
        "en": 'OK — updating to "{left}" and "{right}"…',
    },
    "diagram.update_center.double_bubble.done": {
        "zh": "已更新为「{left}」和「{right}」。",
        "en": 'Updated to "{left}" and "{right}".',
    },
    "diagram.add_node.progress": {
        "zh": "好的，正在添加「{target}」…",
        "en": 'OK — adding "{target}"…',
    },
    "diagram.add_node.done": {
        "zh": "「{target}」已添加。",
        "en": '"{target}" added.',
    },
    "diagram.add_branch.progress": {
        "zh": "好的，正在添加{target}分支并补完…",
        "en": 'OK — adding the "{target}" branch and filling it in…',
    },
    "diagram.add_branch.done": {
        "zh": "{target}分支已补完。",
        "en": 'The "{target}" branch is ready.',
    },
    "diagram.add_child.progress": {
        "zh": "好的，正在添加子项「{target}」…",
        "en": 'OK — adding sub-item "{target}"…',
    },
    "diagram.add_child.done": {
        "zh": "子项「{target}」已添加。",
        "en": 'Sub-item "{target}" added.',
    },
    "diagram.add_child.branch.progress": {
        "zh": "好的，正在向「{branch_label}」分支添加「{target}」…",
        "en": 'OK — adding "{target}" under branch "{branch_label}"…',
    },
    "diagram.add_child.branch.done": {
        "zh": "「{target}」已添加到「{branch_label}」分支。",
        "en": 'Added "{target}" under branch "{branch_label}".',
    },
    "diagram.delete_node.progress": {
        "zh": "好的，正在删除「{target}」…",
        "en": 'OK — removing "{target}"…',
    },
    "diagram.delete_node.done": {
        "zh": "「{target}」已删除。",
        "en": '"{target}" removed.',
    },
    "diagram.delete_branch.progress": {
        "zh": "好的，正在删除「{target}」分支…",
        "en": 'OK — removing branch "{target}"…',
    },
    "diagram.delete_branch.done": {
        "zh": "「{target}」分支已删除。",
        "en": 'Branch "{target}" removed.',
    },
    "diagram.delete_child.progress": {
        "zh": "好的，正在删除子项…",
        "en": "OK — removing the sub-item…",
    },
    "diagram.delete_child.done": {
        "zh": "子项已删除。",
        "en": "Sub-item removed.",
    },
    "diagram.delete_child.branch.progress": {
        "zh": "好的，正在删除「{branch_label}」分支下的子项…",
        "en": 'OK — removing a sub-item under branch "{branch_label}"…',
    },
    "diagram.delete_child.branch.done": {
        "zh": "「{branch_label}」分支下的子项已删除。",
        "en": 'Sub-item under branch "{branch_label}" removed.',
    },
    "diagram.execute_failed": {
        "zh": "抱歉，没能更新这张导图，请换个说法试试。",
        "en": "Sorry, I couldn't update the diagram. Try rephrasing.",
    },
    "diagram.low_confidence": {
        "zh": "你是想{echo}吗？请再说具体一点。",
        "en": "Did you mean to {echo}? Please be a bit more specific.",
    },
    "diagram.low_confidence_generic": {
        "zh": "我不太确定要怎么改这张导图，请再说具体一点。",
        "en": "I'm not sure what to change. Can you be more specific?",
    },
    "diagram.not_understood": {
        "zh": ("没太明白您的意思。我可以帮您改节点、添加或删除分支、更换主题，或打开联想建议——请说一下要改哪个节点。"),
        "en": (
            "I didn't quite catch that. I can rename nodes, add or remove branches, "
            "change the topic, or show inline suggestions — which node should I change?"
        ),
    },
    "diagram.unsupported_type": {
        "zh": (
            "「{requested_type}」还在开发中，暂时可以用{alternative_label}代替。"
            "需要的话，我可以帮您画一张{alternative_label}。"
        ),
        "en": (
            '"{requested_type}" is still in development. For now, try a {alternative_label} instead. '
            "I can help you start a {alternative_label} if you like."
        ),
    },
    "diagram.unsupported_type_unknown": {
        "zh": (
            "暂不支持「{requested_type}」。可以试试{alternative_label}、流程图或气泡图，"
            "需要的话我可以帮您画一张{alternative_label}。"
        ),
        "en": (
            '"{requested_type}" is not supported yet. Try a {alternative_label}, flow map, '
            "or bubble map — I can start a {alternative_label} for you."
        ),
    },
    "ui.auto_complete": {
        "zh": "收到，正在自动补全。",
        "en": "OK — running auto-complete.",
    },
    "ui.start_inline_recommendations": {
        "zh": "好，打开联想建议。",
        "en": "OK — showing inline suggestions.",
    },
    "ui.start_inline_recommendations_no_selection": {
        "zh": "请先在画布上选中一个节点，再说要推荐的内容。",
        "en": "Select a node on the canvas first, then ask for suggestions.",
    },
    "ui.add_node_with_recommendations": {
        "zh": "好，已添加节点，请从推荐里选一个。",
        "en": "OK — node added. Pick one of the suggestions.",
    },
    "ui.open_desktop_canvas.ok": {
        "zh": "好，已在电脑端打开画布。",
        "en": "OK — opening the canvas on desktop.",
    },
    "ui.open_desktop_canvas.fail": {
        "zh": "电脑端暂时打不开画布，请稍后重试。",
        "en": "Couldn't open the desktop canvas right now. Try again shortly.",
    },
    "ui.open_desktop_canvas.unsupported_type": {
        "zh": (
            "电脑端还打不开「{requested_type}」，这个功能还在开发中。"
            "可以先试试{alternative_label}，需要的话我可以帮您在桌面新建一张{alternative_label}。"
        ),
        "en": (
            'Desktop cannot open "{requested_type}" yet — it is still in development. '
            "Try a {alternative_label} for now; I can open one on desktop if you want."
        ),
    },
    "paragraph.processing": {
        "zh": "正在分析段落内容，请稍候…",
        "en": "Analyzing the paragraph — one moment…",
    },
}

_WS_ACTION_TO_DONE_KEY: Dict[str, str] = {
    "update_center": "diagram.update_center.done",
    "update_nodes": "diagram.update_node.done_no_old",
    "add_nodes": "diagram.add_node.done",
    "remove_nodes": "diagram.delete_node.done",
}

_ROUTER_ACTION_TO_PROGRESS_KEY: Dict[str, str] = {
    "update_center": "diagram.update_center.progress",
    "update_node": "diagram.update_node.progress",
    "add_node": "diagram.add_node.progress",
    "delete_node": "diagram.delete_node.progress",
}


def success_key_for_router_action(action: str) -> Optional[str]:
    """Map router action name to progress template key."""
    return _ROUTER_ACTION_TO_PROGRESS_KEY.get(str(action or "").strip())


def _pick_lang(lang: str) -> KittyLanguage:
    return "en" if str(lang).strip().lower().startswith("en") else "zh"


def _apply_slots(template: str, slots: Dict[str, str]) -> str:
    try:
        return template.format_map(_SlotDict(slots))
    except (KeyError, ValueError):
        return template


class _SlotDict(dict[str, str]):
    """format_map helper: missing keys become empty strings."""

    def __missing__(self, key: str) -> str:
        return ""


def render_ack(key: str, slots: Optional[Dict[str, str]] = None, *, lang: str = "zh") -> str:
    """Render a template by key with optional slots."""
    picked = _pick_lang(lang)
    row = _ACK_TEMPLATES.get(key)
    if not row:
        return key
    template = row.get(picked) or row.get("zh") or ""
    if not slots:
        return template
    return _apply_slots(template, slots).strip()


def _resolve_diagram_ack_key(
    action: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
    slots: Dict[str, str],
    *,
    phase: Literal["progress", "done"],
) -> str:
    act = str(action or "").strip()
    if act == "update_node":
        return resolve_update_node_ack_key(slots, phase=phase)
    if act == "update_center":
        return resolve_update_center_ack_key(slots, phase=phase)
    if act == "add_node":
        return resolve_add_node_ack_key(command, session_context, slots, phase=phase)
    if act == "delete_node":
        return resolve_delete_node_ack_key(command, session_context, slots, phase=phase)
    fallback = success_key_for_router_action(act)
    if fallback:
        if phase == "done":
            done_key = _WS_ACTION_TO_DONE_KEY.get(_router_action_to_ws_action(act) or "")
            if done_key:
                return done_key
        return fallback
    return "diagram.not_understood"


def _router_action_to_ws_action(router_action: str) -> Optional[str]:
    mapping = {
        "update_center": "update_center",
        "update_node": "update_nodes",
        "add_node": "add_nodes",
        "delete_node": "remove_nodes",
    }
    return mapping.get(router_action)


def render_ack_for_command(
    action: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]] = None,
    *,
    lang: str = "zh",
    phase: Literal["progress", "done"] = "progress",
) -> str:
    """Render success/clarify ack for a router-level command."""
    act = str(action or "").strip()
    slots = slots_from_command(act, command, session_context)
    key = _resolve_diagram_ack_key(act, command, session_context, slots, phase=phase)
    if key == "diagram.not_understood":
        return render_ack(key, lang=lang)
    return render_ack(key, slots, lang=lang)


def render_ack_for_diagram_update(
    action: str,
    updates: Any,
    *,
    lang: str = "zh",
    command: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Render user_summary for diagram_update WS payloads."""
    if command and session_context is not None:
        router_action = _ws_action_to_router_action(str(action or ""))
        if router_action:
            return render_ack_for_command(
                router_action,
                command,
                session_context,
                lang=lang,
                phase="done",
            )

    act = str(action or "").strip()
    slots = slots_from_diagram_update(act, updates)
    router_action = _ws_action_to_router_action(act)
    if router_action:
        cmd = command if isinstance(command, dict) else {}
        key = _resolve_diagram_ack_key(
            router_action,
            cmd,
            session_context,
            slots,
            phase="done",
        )
        if key != "diagram.not_understood":
            return render_ack(key, slots, lang=lang)

    key = _WS_ACTION_TO_DONE_KEY.get(act)
    if act == "update_nodes" and slots.get("old_text") and slots.get("new_text"):
        key = "diagram.update_node.done"
    if act == "update_center" and slots.get("left") and slots.get("right"):
        key = "diagram.update_center.double_bubble.done"
    if not key:
        key = "diagram.update_center.done"
    return render_ack(key, slots, lang=lang)


def render_low_confidence_ack(
    command: Dict[str, Any],
    *,
    lang: str = "zh",
    session_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Clarify template with echo-back when slots are available."""
    action = str(command.get("action") or "").strip()
    slots = slots_from_command(action, command, session_context)
    echo = echo_hint_from_slots(slots, lang=_pick_lang(lang))
    if echo:
        return render_ack("diagram.low_confidence", {"echo": echo}, lang=lang)
    return render_ack("diagram.low_confidence_generic", lang=lang)


def render_unsupported_diagram_ack(
    match: UnsupportedAckMatch,
    *,
    lang: str = "zh",
    desktop_open: bool = False,
) -> str:
    """Render in-development fallback for unsupported diagram type requests."""
    slots = {
        "requested_type": str(match.get("requested_type") or ""),
        "alternative_label": str(match.get("alternative_label") or ""),
    }
    entry_id = str(match.get("entry_id") or "")
    if desktop_open:
        key = "ui.open_desktop_canvas.unsupported_type"
    elif entry_id == "unknown":
        key = "diagram.unsupported_type_unknown"
    else:
        key = "diagram.unsupported_type"
    return render_ack(key, slots, lang=lang)


def render_not_understood_ack(*, lang: str = "zh") -> str:
    """Render clarify ack when intent is outside the node-action catalog."""
    return render_ack("diagram.not_understood", lang=lang)


def _ws_action_to_router_action(ws_action: str) -> Optional[str]:
    mapping = {
        "update_center": "update_center",
        "update_nodes": "update_node",
        "add_nodes": "add_node",
        "remove_nodes": "delete_node",
    }
    return mapping.get(ws_action)
