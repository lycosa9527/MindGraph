"""Pending clarify-options pick after ambiguous node-action routing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack
from services.kitty.context.messaging import (
    resolve_voice_interaction_language,
)
from services.kitty.routing.node_action_debug import (
    clip_node_action_text,
    log_node_action,
    log_node_action_debug,
    summarize_legacy_command,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.runtime_state import voice_sessions

PENDING_CLARIFY_OPTIONS_KEY = "pending_clarify_options"

_BOOK_QUOTE_RE = re.compile(r"「([^」]+)」")
# ``update_node.target`` is the *new* text — never seed it from the question quote
# (that quote is usually the old label). Only share identity labels across options.
_ACTIONS_NEEDING_TARGET_SEED = frozenset(
    {
        "add_node",
        "delete_node",
        "auto_complete_branch",
    }
)

_ORDINAL_ZH = {
    "一": 1,
    "二": 2,
    "三": 3,
    "1": 1,
    "2": 2,
    "3": 3,
}
_PICK_RE = re.compile(
    r"^(?:选|选择|要|第)?\s*([123一二三])"
    r"(?:个|项|条|种)?"
    r"(?:吧|的|选项)?$"
)
_FIRST_RE = re.compile(
    r"^(?:好的?)?(?:就)?(?:选|要)?(?:第一个|第1个|1号|option\s*1|the\s+first)$",
    re.IGNORECASE,
)
_SECOND_RE = re.compile(
    r"^(?:好的?)?(?:就)?(?:选|要)?(?:第二个|第2个|2号|option\s*2|the\s+second)$",
    re.IGNORECASE,
)
_THIRD_RE = re.compile(
    r"^(?:好的?)?(?:就)?(?:选|要)?(?:第三个|第3个|3号|option\s*3|the\s+third)$",
    re.IGNORECASE,
)


def get_pending_clarify_options(session: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return pending clarify payload when armed."""
    if not isinstance(session, dict):
        return None
    raw = session.get(PENDING_CLARIFY_OPTIONS_KEY)
    if not isinstance(raw, dict):
        return None
    commands = raw.get("option_commands")
    if not isinstance(commands, list) or len(commands) < 2:
        return None
    return dict(raw)


def clear_pending_clarify_options(session: Optional[Dict[str, Any]]) -> None:
    """Drop pending clarify-options state."""
    if isinstance(session, dict):
        session.pop(PENDING_CLARIFY_OPTIONS_KEY, None)


def _first_book_quote(text: str) -> str:
    match = _BOOK_QUOTE_RE.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def seed_target_from_clarify_command(command: Dict[str, Any]) -> str:
    """
    Recover the node label the clarify turn is about.

    LLMs often omit ``target`` on placement-only options (e.g. 「作为新的顶级分支」)
    while sibling options still carry it — or the question quotes the label.
    """
    option_commands = command.get("option_commands")
    if isinstance(option_commands, list):
        for item in option_commands:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action") or "").strip()
            if action not in _ACTIONS_NEEDING_TARGET_SEED:
                continue
            target = item.get("target")
            if isinstance(target, str) and target.strip():
                return target.strip()

    question = command.get("question")
    if isinstance(question, str) and question.strip():
        quoted = _first_book_quote(question)
        if quoted:
            return quoted

    labels = command.get("options")
    if isinstance(labels, list):
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                continue
            # Placement-only labels quote the *parent* (「作为「品牌」的子节点」), not the
            # node being added — never seed from those.
            if label.strip().startswith("作为") or "作为新的" in label:
                continue
            if not any(token in label for token in ("新增", "添加", "补全", "删除", "加")):
                continue
            quoted = _first_book_quote(label)
            if quoted:
                return quoted
    return ""


def _backfill_option_command_targets(
    option_commands: List[Dict[str, Any]],
    seed_target: str,
) -> List[Dict[str, Any]]:
    if not seed_target:
        return [dict(c) for c in option_commands]
    filled: List[Dict[str, Any]] = []
    for raw in option_commands:
        cmd = dict(raw)
        action = str(cmd.get("action") or "").strip()
        if action in _ACTIONS_NEEDING_TARGET_SEED:
            existing = cmd.get("target")
            if not (isinstance(existing, str) and existing.strip()):
                cmd["target"] = seed_target
        filled.append(cmd)
    return filled


def arm_pending_clarify_options(
    session: Optional[Dict[str, Any]],
    command: Dict[str, Any],
) -> bool:
    """Arm pending clarify after router emits options. Returns True when armed."""
    if not isinstance(session, dict):
        return False
    option_commands = command.get("option_commands")
    if not isinstance(option_commands, list) or len(option_commands) < 2:
        return False
    labels = command.get("options")
    label_list: List[str] = []
    if isinstance(labels, list):
        for item in labels:
            if isinstance(item, str) and item.strip():
                label_list.append(item.strip())
    raw_cmds = [dict(c) for c in option_commands if isinstance(c, dict)]
    if len(raw_cmds) < 2:
        return False
    seed_target = seed_target_from_clarify_command(
        {
            "question": command.get("question"),
            "options": label_list,
            "option_commands": raw_cmds,
        }
    )
    filled_cmds = _backfill_option_command_targets(raw_cmds, seed_target)
    pending: Dict[str, Any] = {
        "question": command.get("question"),
        "options": label_list,
        "option_commands": filled_cmds,
    }
    if seed_target:
        pending["seed_target"] = seed_target
    session[PENDING_CLARIFY_OPTIONS_KEY] = pending
    log_node_action_debug(
        "clarify_armed",
        detail=f"options={len(label_list)}",
        extra={"labels": label_list[:3], "seed_target": seed_target or None},
    )
    return True


def classify_clarify_option_pick(text: str, option_count: int) -> Optional[int]:
    """Return 1-based option index when user picks, else None."""
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned or option_count < 2:
        return None
    if _FIRST_RE.match(cleaned):
        return 1
    if option_count >= 2 and _SECOND_RE.match(cleaned):
        return 2
    if option_count >= 3 and _THIRD_RE.match(cleaned):
        return 3
    pick = _PICK_RE.match(cleaned)
    if pick:
        idx = _ORDINAL_ZH.get(pick.group(1))
        if isinstance(idx, int) and 1 <= idx <= option_count:
            return idx
    if cleaned.isdigit():
        idx = int(cleaned)
        if 1 <= idx <= option_count:
            return idx
    return None


async def try_consume_pending_clarify_options(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    If clarify options are pending, consume a numbered pick.

    Returns the chosen legacy command dict when consumed, otherwise ``None``.
    """
    live = voice_sessions.get(voice_session_id)
    pending = get_pending_clarify_options(live if isinstance(live, dict) else None)
    if pending is None:
        return None

    log_node_action_debug(
        "clarify_pending_seen",
        voice_session_id=voice_session_id,
        detail=clip_node_action_text(command_text),
        extra={"option_count": len(pending.get("option_commands") or [])},
    )

    commands = pending.get("option_commands")
    if not isinstance(commands, list):
        clear_pending_clarify_options(live if isinstance(live, dict) else None)
        log_node_action_debug(
            "clarify_cleared",
            voice_session_id=voice_session_id,
            detail="invalid option_commands",
        )
        return None

    pick = classify_clarify_option_pick(command_text, len(commands))
    if pick is None:
        clear_pending_clarify_options(live if isinstance(live, dict) else None)
        log_node_action(
            "clarify_unrecognized_reply",
            voice_session_id=voice_session_id,
            detail=clip_node_action_text(command_text),
            extra={"option_count": len(commands)},
        )
        return None

    chosen = commands[pick - 1]
    if not isinstance(chosen, dict):
        clear_pending_clarify_options(live if isinstance(live, dict) else None)
        log_node_action_debug(
            "clarify_cleared",
            voice_session_id=voice_session_id,
            detail=f"invalid command at pick={pick}",
        )
        return None

    clear_pending_clarify_options(live if isinstance(live, dict) else None)
    log_node_action(
        "clarify_picked",
        voice_session_id=voice_session_id,
        detail=f"pick={pick} {summarize_legacy_command(chosen)}",
        action=str(chosen.get("action") or "") or None,
        extra={"option_index": pick},
    )
    lang = resolve_voice_interaction_language(session_context)
    labels = pending.get("options")
    label = ""
    if isinstance(labels, list) and pick - 1 < len(labels):
        raw_label = labels[pick - 1]
        if isinstance(raw_label, str):
            label = raw_label.strip()
    ack_text = render_ack(
        "diagram.clarify_options.picked",
        {"label": label or str(chosen.get("action") or "")},
        lang=lang,
    )
    await emit_user_ack(
        websocket,
        voice_session_id,
        ack_text,
        one_sentence_action=str(chosen.get("action") or ""),
        one_sentence_outcome="executed",
        one_sentence_user_text=command_text,
        # Bridge ack before the real edit result — text only; TTS would be cut
        # off by the following final (industry: speak the terminal utterance).
        reply_kind="progress",
    )
    memory = get_session_memory(voice_session_id)
    memory.append_action_turn(ack_text, action=str(chosen.get("action") or ""))
    picked = dict(chosen)
    seed_raw = pending.get("seed_target")
    seed = seed_raw.strip() if isinstance(seed_raw, str) else ""
    action = str(picked.get("action") or "").strip()
    if seed and action in _ACTIONS_NEEDING_TARGET_SEED:
        existing = picked.get("target")
        if not (isinstance(existing, str) and existing.strip()):
            picked["target"] = seed
    return picked
