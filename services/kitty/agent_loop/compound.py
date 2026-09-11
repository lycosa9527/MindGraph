"""Apply an already-planned stack (placeholder rename) in order, one office line.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.diagram_edit.transport.kitty_ws import MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack
from services.kitty.agent_loop.intent_clarify import (
    PENDING_INTENT_SLOT_KEY,
    is_intent_slot_cancel,
)
from services.kitty.agent_loop.tools import dispatch_prepared_command
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.routing.one_sentence_edit_heuristics import split_multi_labels
from services.kitty.routing.outcomes import RouteOutcome, RouteResult
from services.kitty.session.runtime_state import voice_sessions


@dataclass(slots=True)
class CompoundPlan:
    """Ordered structural steps (placeholder rename after an armed slot)."""

    steps: List[Dict[str, Any]] = field(default_factory=list)
    kind: str = "named"
    remaining_ask: bool = False


def take_placeholder_rename_plan(
    session: Optional[Dict[str, Any]],
    text: str,
) -> Optional[CompoundPlan]:
    """Map the next utterance onto armed placeholder node ids."""
    if not isinstance(session, dict):
        return None
    raw = session.get(PENDING_INTENT_SLOT_KEY)
    if not isinstance(raw, dict):
        return None
    node_ids = _clean_ids(raw.get("node_ids"))
    if not node_ids:
        return None
    if is_intent_slot_cancel(text):
        return None
    labels = split_multi_labels(text)
    if len(labels) < 2:
        filled = text.strip()
        labels = [filled] if filled else []
    steps: List[Dict[str, Any]] = []
    for index, label in enumerate(labels):
        if index >= len(node_ids):
            break
        steps.append(
            {
                "action": "update_node",
                "node_id": node_ids[index],
                "target": node_ids[index],
                "new_text": label,
                "confidence": 0.9,
            }
        )
    if not steps:
        return None
    remaining = node_ids[len(steps) :]
    if remaining:
        raw["node_ids"] = remaining
        session[PENDING_INTENT_SLOT_KEY] = raw
    else:
        session.pop(PENDING_INTENT_SLOT_KEY, None)
    return CompoundPlan(steps=steps, kind="rename", remaining_ask=bool(remaining))


async def run_compound_plan(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    plan: CompoundPlan,
    session_context: Dict[str, Any],
    diagram_type: str,
    command_text: str,
    verify_required: bool,
    lang: str,
) -> RouteResult:
    """Speak one office line, then apply each step with skip_ack."""
    steps = list(plan.steps)
    if not steps:
        return _finish(voice_session_id, RouteOutcome.FAILED, reason="compound_empty")
    live = voice_sessions.get(voice_session_id)
    if isinstance(live, dict):
        live[MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY] = True
    last_action = str(steps[0].get("action") or "")
    try:
        ack_text = render_ack(
            "diagram.multi_step.done",
            {"detail": _detail_line(steps, plan, lang=lang)},
            lang=lang,
        )
        if ack_text:
            await emit_user_ack(
                websocket,
                voice_session_id,
                ack_text,
                one_sentence_action="multi_step",
                one_sentence_outcome="executed",
                one_sentence_user_text=command_text,
            )
        for command in steps:
            context = _live_context(voice_session_id, session_context)
            dispatched = await dispatch_prepared_command(
                websocket,
                voice_session_id,
                command=command,
                session_context=context,
                diagram_type=diagram_type,
                command_text=command_text,
                verify_required=verify_required,
                grounding_source="ask_followup" if plan.kind == "rename" else "compound",
                skip_ack=True,
            )
            last_action = dispatched.action or str(command.get("action") or "")
            if not dispatched.mutated:
                return _finish(
                    voice_session_id,
                    RouteOutcome.FAILED,
                    reason="failed",
                    action=last_action,
                )
    finally:
        live_clear = voice_sessions.get(voice_session_id)
        if isinstance(live_clear, dict):
            live_clear.pop(MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY, None)
    reason = "slot_rename" if plan.kind == "rename" else "compound"
    return _finish(voice_session_id, RouteOutcome.EXECUTED, reason=reason, action=last_action)


def _clean_ids(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def _quote(label: str, lang: str) -> str:
    return f'"{label}"' if lang == "en" else f"「{label}」"


def _detail_line(steps: List[Dict[str, Any]], plan: CompoundPlan, *, lang: str) -> str:
    use_en = lang == "en"
    if plan.kind == "rename":
        names = [str(step.get("new_text") or "") for step in steps]
        quoted = "".join(_quote(name, lang) for name in names if name)
        if use_en:
            ask = " What should the other one be called?" if plan.remaining_ask else ""
            return f"renaming to {quoted}.{ask}".strip()
        ask = "另一条叫什么？" if plan.remaining_ask else ""
        return f"改成{quoted}。{ask}"
    bits: List[str] = []
    adds: List[str] = []
    for step in steps:
        action = str(step.get("action") or "")
        if action == "update_center":
            topic = str(step.get("target") or "")
            bits.append(f"topic is {_quote(topic, lang)}" if use_en else f"主题换成{_quote(topic, lang)}")
        elif action == "add_node":
            adds.append(str(step.get("target") or ""))
        elif action == "delete_node":
            label = str(step.get("target") or "")
            bits.append(f"removing {_quote(label, lang)}" if use_en else f"删掉{_quote(label, lang)}")
        elif action == "update_node":
            old = str(step.get("target") or "")
            new = str(step.get("new_text") or "")
            bits.append(
                f"{_quote(old, lang)} is now {_quote(new, lang)}"
                if use_en
                else f"{_quote(old, lang)}改成{_quote(new, lang)}"
            )
    if adds:
        quoted = "".join(_quote(label, lang) for label in adds if label)
        bits.append(f"adding {quoted}" if use_en else f"加上{quoted}")
    joiner = ", " if use_en else "，"
    detail = joiner.join(bit for bit in bits if bit)
    if use_en and not detail.endswith("?"):
        return f"{detail}."
    if not use_en and not detail.endswith("？") and not detail.endswith("。"):
        return f"{detail}。"
    return detail


def _live_context(voice_session_id: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    live = voice_sessions.get(voice_session_id)
    if isinstance(live, dict):
        raw = live.get("context")
        if isinstance(raw, dict):
            return raw
    return fallback


def _finish(
    voice_session_id: str,
    outcome: RouteOutcome,
    *,
    reason: str = "",
    action: str = "",
) -> RouteResult:
    kitty_wf_log(
        "agent_loop",
        reason or outcome.value,
        voice_session_id=voice_session_id,
        action=action or None,
    )
    return RouteResult(outcome=outcome, reason=reason or None, action=action or None)
