"""Background branch auto-complete after mind-map branch add; legacy yes/no offer consume.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, Literal, Optional

from fastapi import WebSocket

from services.kitty.ack.ack_action_resolve import classify_add_node_variant
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack
from services.kitty.context.messaging import (
    resolve_voice_interaction_language,
    safe_websocket_send,
)
from services.kitty.infra.desktop.kitty_voice_command_fanout import fanout_voice_command_from_session
from services.kitty.routing.one_sentence_edit_heuristics import (
    heuristic_one_sentence_edit_command,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.runtime_state import voice_sessions

PENDING_BRANCH_AUTOCOMPLETE_KEY = "pending_branch_autocomplete"

OfferReply = Literal["accept", "decline", "other"]

_AFFIRM_EXACT = frozenset(
    {
        "好",
        "好的",
        "行",
        "可以",
        "要",
        "需要",
        "要的",
        "补全",
        "自动补全",
        "帮我补全",
        "请补全",
        "yes",
        "y",
        "ok",
        "okay",
        "sure",
        "please",
        "do it",
        "go ahead",
        "yeah",
        "yep",
    }
)
_DECLINE_EXACT = frozenset(
    {
        "不",
        "不用",
        "不要",
        "先不用",
        "暂时不用",
        "算了",
        "否",
        "no",
        "n",
        "nope",
        "nah",
        "skip",
        "later",
        "not now",
    }
)
_AFFIRM_RE = re.compile(
    r"(好的?|可以|需要|要补全|自动补全|帮我补全|请补全|\byes\b|\bok\b|\bokay\b|\bsure\b)",
    re.IGNORECASE,
)
_DECLINE_RE = re.compile(
    r"(不用|不要|先不用|暂时不用|算了|\bno\b|\bnope\b|\bskip\b|not now)",
    re.IGNORECASE,
)


def get_pending_branch_autocomplete(session: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Return pending offer payload when armed."""
    if not isinstance(session, dict):
        return None
    raw = session.get(PENDING_BRANCH_AUTOCOMPLETE_KEY)
    if not isinstance(raw, dict):
        return None
    target = raw.get("target")
    if not isinstance(target, str) or not target.strip():
        return None
    return {"target": target.strip()}


def clear_pending_branch_autocomplete(session: Optional[Dict[str, Any]]) -> None:
    """Drop pending branch auto-complete offer."""
    if isinstance(session, dict):
        session.pop(PENDING_BRANCH_AUTOCOMPLETE_KEY, None)


def created_node_id_from_applied_ops(applied_ops: Any) -> str | None:
    """Extract canvas node_id from Diagram Edit Tool applied_ops."""
    if not isinstance(applied_ops, list) or not applied_ops:
        return None
    first = applied_ops[0]
    if not isinstance(first, dict):
        return None
    node_id = first.get("node_id")
    if isinstance(node_id, str) and node_id.strip():
        return node_id.strip()
    return None


def arm_pending_branch_autocomplete(
    session: Optional[Dict[str, Any]],
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
) -> bool:
    """Arm offer after a successful mind-map branch add. Returns True when armed."""
    if not isinstance(session, dict):
        return False
    if classify_add_node_variant(command, session_context) != "branch":
        return False
    target = command.get("target")
    if not isinstance(target, str) or not target.strip():
        return False
    session[PENDING_BRANCH_AUTOCOMPLETE_KEY] = {"target": target.strip()}
    return True


def classify_branch_autocomplete_offer_reply(text: str) -> OfferReply:
    """Classify a short yes/no reply to the branch auto-complete offer."""
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned:
        return "other"
    lowered = cleaned.lower()
    if cleaned in _DECLINE_EXACT or lowered in _DECLINE_EXACT:
        return "decline"
    if cleaned in _AFFIRM_EXACT or lowered in _AFFIRM_EXACT:
        return "accept"
    if _DECLINE_RE.search(cleaned):
        return "decline"
    if _AFFIRM_RE.search(cleaned) and len(cleaned) <= 24:
        return "accept"
    return "other"


async def emit_auto_complete_branch(
    websocket: WebSocket,
    voice_session_id: str,
    target: str,
    *,
    command_text: str = "",
    lang: str = "zh",
    node_id: str | None = None,
    silent_ack: bool = False,
) -> None:
    """Send canvas branch auto-complete action; optionally skip chat progress ack."""
    label = str(target or "").strip()
    params: Dict[str, Any] = {"node_label": label}
    if isinstance(node_id, str) and node_id.strip():
        params["node_id"] = node_id.strip()
    await safe_websocket_send(
        websocket,
        {"type": "action", "action": "auto_complete_branch", "params": params},
    )
    await fanout_voice_command_from_session(
        voice_session_id,
        "auto_complete_branch",
        params=params,
    )
    if silent_ack:
        return
    ack_text = render_ack(
        "diagram.branch_autocomplete.accepted",
        {"target": label},
        lang=lang,
    )
    await emit_user_ack(
        websocket,
        voice_session_id,
        ack_text,
        one_sentence_action="auto_complete_branch",
        one_sentence_outcome="pending",
        one_sentence_user_text=command_text or None,
        reply_kind="progress",
    )
    memory = get_session_memory(voice_session_id)
    memory.append_action_turn(ack_text, action="auto_complete_branch")


async def maybe_start_background_branch_autocomplete(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
    *,
    command_text: str = "",
    node_id: str | None = None,
) -> bool:
    """
    After a successful mind-map branch add, start auto-complete without asking.

    Returns True when the canvas action was emitted. Does not arm the yes/no offer.
    ``node_id`` must be the real canvas id from the verified apply result when known.
    """
    if classify_add_node_variant(command, session_context) != "branch":
        return False
    target = command.get("target")
    if not isinstance(target, str) or not target.strip():
        return False
    resolved_id = node_id.strip() if isinstance(node_id, str) and node_id.strip() else None
    lang = resolve_voice_interaction_language(session_context if isinstance(session_context, dict) else {})
    await emit_auto_complete_branch(
        websocket,
        voice_session_id,
        target.strip(),
        command_text=command_text,
        lang=lang,
        node_id=resolved_id,
        silent_ack=True,
    )
    return True


async def try_consume_pending_branch_autocomplete(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
) -> Optional[str]:
    """
    If a branch auto-complete offer is pending, consume a yes/no reply.

    Returns the handled action name (``auto_complete_branch`` / ``decline_branch_autocomplete``)
    when consumed, otherwise ``None`` so normal routing continues.
    """
    live = voice_sessions.get(voice_session_id)
    pending = get_pending_branch_autocomplete(live if isinstance(live, dict) else None)
    if pending is None:
        return None

    # Explicit "补全X分支" must not be treated as a vague yes/no — clear offer and
    # let the normal router/heuristic handle the named branch.
    heuristic = heuristic_one_sentence_edit_command(command_text)
    if heuristic and heuristic.get("action") == "auto_complete_branch":
        clear_pending_branch_autocomplete(live if isinstance(live, dict) else None)
        return None

    reply = classify_branch_autocomplete_offer_reply(command_text)
    if reply == "other":
        clear_pending_branch_autocomplete(live if isinstance(live, dict) else None)
        return None

    clear_pending_branch_autocomplete(live if isinstance(live, dict) else None)
    lang = resolve_voice_interaction_language(session_context)
    target = pending["target"]
    slots = {"target": target}

    if reply == "decline":
        ack_text = render_ack("diagram.branch_autocomplete.declined", slots, lang=lang)
        await emit_user_ack(
            websocket,
            voice_session_id,
            ack_text,
            one_sentence_action="decline_branch_autocomplete",
            one_sentence_outcome="executed",
            one_sentence_user_text=command_text,
        )
        memory = get_session_memory(voice_session_id)
        memory.append_action_turn(ack_text, action="decline_branch_autocomplete")
        return "decline_branch_autocomplete"

    await emit_auto_complete_branch(
        websocket,
        voice_session_id,
        target,
        command_text=command_text,
        lang=lang,
    )
    return "auto_complete_branch"
