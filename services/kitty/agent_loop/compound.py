"""Stacked one-sentence edits: split, speak once, apply in order.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.diagram_edit.transport.kitty_ws import MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack
from services.kitty.agent_loop.intent_clarify import (
    PENDING_INTENT_SLOT_KEY,
    arm_pending_intent_slot,
    is_intent_slot_cancel,
    persist_armed_intent_slot,
)
from services.kitty.agent_loop.results import created_node_ids_from_payload
from services.kitty.agent_loop.tools import dispatch_prepared_command
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.routing.one_sentence_edit_heuristics import (
    heuristic_one_sentence_edit_command,
    split_multi_labels,
)
from services.kitty.routing.outcomes import RouteOutcome, RouteResult
from services.kitty.session.runtime_state import voice_sessions

_STRUCTURAL = frozenset({"update_center", "add_node", "update_node", "delete_node"})
_BLOCKED = frozenset({"auto_complete", "auto_complete_branch"})
_CLAUSE_SPLIT = re.compile(
    r"(?:[，,、]\s*)?(?:然后|并且|and then|, then|再)",
    re.IGNORECASE,
)
_COUNT_ONLY_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?P<count>[两三四五2-4])个"
    r"(?:新的)?(?:分支|节点)$"
)
_COUNT_ONLY_EN = re.compile(
    r"^(?:please\s+)?(?:add|create)\s+"
    r"(?P<count>two|three|four|[2-4])\s+"
    r"(?:new\s+)?(?:branches|nodes)$",
    re.IGNORECASE,
)
_COUNT_LIST_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?P<count>[两三四五2-4])个"
    r"(?:新的)?(?:分支|节点)"
    r"(?:：|:)\s*(?P<labels>.+)$"
)
_COUNT_LIST_EN = re.compile(
    r"^(?:please\s+)?(?:add|create)\s+"
    r"(?P<count>two|three|four|[2-4])\s+"
    r"(?:new\s+)?(?:branches|nodes)\s*:\s*(?P<labels>.+)$",
    re.IGNORECASE,
)
_ADD_LIST_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:以下|这些|几个)?"
    r"(?:分支|节点)?"
    r"(?:：|:|为)?"
    r"\s*(?P<labels>.+?(?:[、，,]|和|&).+?)"
    r"(?:这?[二三四五六七八九十\d]+个)?"
    r"(?:分支|节点)?$"
)
_ZH_COUNT = {"两": 2, "二": 2, "三": 3, "四": 4, "2": 2, "3": 3, "4": 4}
_EN_COUNT = {"two": 2, "three": 3, "four": 4, "2": 2, "3": 3, "4": 4}
_ZH_COUNT_WORD = {2: "两", 3: "三", 4: "四"}
_MIN_PLACEHOLDERS = 2
_MAX_PLACEHOLDERS = 4


@dataclass(slots=True)
class CompoundPlan:
    """Ordered structural steps, or a vague count that becomes placeholders."""

    steps: List[Dict[str, Any]] = field(default_factory=list)
    kind: str = "named"
    placeholder_count: int = 0
    remaining_ask: bool = False


def parse_compound_turn(text: str) -> Optional[CompoundPlan]:
    """Split on 再/然后/并且 and parse each clause. None leaves the turn to Qwen."""
    clauses = _split_clauses(text)
    named: List[Dict[str, Any]] = []
    vague_count = 0
    if len(clauses) == 1:
        return _plan_from_single_clause(clauses[0])
    for clause in clauses:
        parsed = _parse_clause(clause)
        if parsed is None:
            return None
        count, steps = parsed
        if count:
            if vague_count or steps:
                return None
            vague_count = count
            continue
        named.extend(steps)
    return _finish_plan(named, vague_count)


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
    if plan.placeholder_count:
        labels = _unique_placeholders(
            plan.placeholder_count,
            lang=lang,
            existing=_existing_labels(session_context),
        )
        steps.extend({"action": "add_node", "target": label, "confidence": 0.92} for label in labels)
    if not steps:
        return _finish(voice_session_id, RouteOutcome.FAILED, reason="fast_compound_empty")
    placeholder_from = len(steps) - plan.placeholder_count
    live = voice_sessions.get(voice_session_id)
    if isinstance(live, dict):
        live[MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY] = True
    created: List[str] = []
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
        for index, command in enumerate(steps):
            context = _live_context(voice_session_id, session_context)
            is_placeholder = plan.placeholder_count > 0 and index >= placeholder_from
            source = "ask_followup" if is_placeholder or plan.kind == "rename" else "fast_compound"
            dispatched = await dispatch_prepared_command(
                websocket,
                voice_session_id,
                command=command,
                session_context=context,
                diagram_type=diagram_type,
                command_text=command_text,
                verify_required=verify_required,
                grounding_source=source,
                skip_ack=True,
                skip_background_autocomplete=is_placeholder,
            )
            last_action = dispatched.action or str(command.get("action") or "")
            if not dispatched.mutated:
                return _finish(
                    voice_session_id,
                    RouteOutcome.FAILED,
                    reason="failed",
                    action=last_action,
                )
            if is_placeholder:
                created.extend(
                    _placeholder_created_ids(
                        dispatched.payload,
                        voice_session_id,
                        command,
                    )
                )
        if plan.placeholder_count:
            await _arm_placeholder_slot(voice_session_id, created, lang=lang)
    finally:
        live_clear = voice_sessions.get(voice_session_id)
        if isinstance(live_clear, dict):
            live_clear.pop(MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY, None)
    reason = "fast_compound_vague" if plan.placeholder_count else "fast_compound"
    return _finish(voice_session_id, RouteOutcome.EXECUTED, reason=reason, action=last_action)


def _split_clauses(text: str) -> List[str]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    parts = [part.strip() for part in _CLAUSE_SPLIT.split(stripped) if part and part.strip()]
    return parts or [stripped]


def _plan_from_single_clause(clause: str) -> Optional[CompoundPlan]:
    parsed = _parse_clause(clause)
    if parsed is None:
        return None
    count, steps = parsed
    return _finish_plan(steps, count)


def _finish_plan(named: List[Dict[str, Any]], vague_count: int) -> Optional[CompoundPlan]:
    if vague_count:
        return CompoundPlan(steps=named, kind="vague", placeholder_count=vague_count)
    if len(named) >= 2:
        return CompoundPlan(steps=named, kind="named")
    return None


def _parse_clause(clause: str) -> Optional[tuple[int, List[Dict[str, Any]]]]:
    """Return (vague_count, named_steps) or None when the clause is blocked/unknown."""
    listed = _parse_count_list(clause)
    if listed is not None:
        return 0, listed
    count = _parse_count_only(clause)
    if count:
        return count, []
    heuristic = heuristic_one_sentence_edit_command(clause)
    if heuristic is not None:
        flattened = _flatten_heuristic(heuristic)
        if flattened is None:
            return None
        return 0, flattened
    added = _parse_add_list(clause)
    if added:
        return 0, added
    return None


def _flatten_heuristic(command: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    action = str(command.get("action") or "").strip()
    follows_raw = command.get("follow_up_actions")
    follows = [item for item in follows_raw if isinstance(item, dict)] if isinstance(follows_raw, list) else []
    if action in _BLOCKED or any(str(item.get("action") or "") in _BLOCKED for item in follows):
        return None
    if action not in _STRUCTURAL or not _is_valued(command):
        return []
    steps = [_strip_follows(command)]
    for item in follows:
        follow_action = str(item.get("action") or "").strip()
        if follow_action not in _STRUCTURAL or not _is_valued(item):
            return None
        steps.append(_strip_follows(item))
    return steps


def _parse_count_only(clause: str) -> int:
    for pattern, table in ((_COUNT_ONLY_ZH, _ZH_COUNT), (_COUNT_ONLY_EN, _EN_COUNT)):
        match = pattern.match(clause)
        if match is None:
            continue
        count = table.get(match.group("count").lower(), 0)
        if _MIN_PLACEHOLDERS <= count <= _MAX_PLACEHOLDERS:
            return count
    return 0


def _parse_count_list(clause: str) -> Optional[List[Dict[str, Any]]]:
    for pattern in (_COUNT_LIST_ZH, _COUNT_LIST_EN):
        match = pattern.match(clause)
        if match is None:
            continue
        labels = split_multi_labels(match.group("labels"))
        if len(labels) >= 2:
            return [_add_step(label) for label in labels]
    return None


def _parse_add_list(clause: str) -> List[Dict[str, Any]]:
    match = _ADD_LIST_ZH.match(clause)
    if match is None:
        return []
    labels = split_multi_labels(match.group("labels"))
    if len(labels) < 2:
        return []
    return [_add_step(label) for label in labels]


def _add_step(label: str) -> Dict[str, Any]:
    return {"action": "add_node", "target": label, "confidence": 0.92}


def _strip_follows(command: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(command)
    cleaned.pop("follow_up_actions", None)
    return cleaned


def _is_valued(command: Dict[str, Any]) -> bool:
    action = str(command.get("action") or "").strip()
    if action == "update_node":
        new_text = command.get("new_text")
        return isinstance(new_text, str) and bool(new_text.strip()) and bool(_referent(command))
    if action == "delete_node":
        return bool(_referent(command))
    target = command.get("target")
    return isinstance(target, str) and bool(target.strip())


def _referent(command: Dict[str, Any]) -> bool:
    for key in ("target", "node_id"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            return True
    return False


def _clean_ids(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def _placeholder_created_ids(
    payload: Dict[str, Any],
    voice_session_id: str,
    command: Dict[str, Any],
) -> List[str]:
    ids = created_node_ids_from_payload(payload)
    if ids:
        return ids
    label = str(command.get("target") or "").strip()
    found = _node_id_for_label(_live_context(voice_session_id, {}), label)
    if found:
        return [found]
    return []


def _node_id_for_label(session_context: Dict[str, Any], label: str) -> str:
    wanted = label.strip()
    if not wanted:
        return ""
    diagram = session_context.get("diagram_data")
    if not isinstance(diagram, dict):
        return ""
    for key in ("children", "nodes"):
        rows = diagram.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = row.get("text")
            node_id = row.get("id")
            if text == wanted and isinstance(node_id, str) and node_id.strip() and node_id != "topic":
                return node_id.strip()
    return ""


def _existing_labels(session_context: Dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    diagram = session_context.get("diagram_data")
    if not isinstance(diagram, dict):
        return labels
    center = diagram.get("center")
    if isinstance(center, dict):
        text = center.get("text")
        if isinstance(text, str) and text.strip():
            labels.add(text.strip())
    for key in ("children", "nodes"):
        rows = diagram.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = row.get("text")
            if isinstance(text, str) and text.strip():
                labels.add(text.strip())
    return labels


def _unique_placeholders(count: int, *, lang: str, existing: set[str]) -> List[str]:
    taken = set(existing)
    labels: List[str] = []
    index = 0
    while len(labels) < count and index < 20:
        if lang == "en":
            label = "New branch" if index == 0 else f"New branch {index + 1}"
        else:
            label = "新分支" if index == 0 else f"新分支{index + 1}"
        index += 1
        if label in taken:
            continue
        taken.add(label)
        labels.append(label)
    return labels


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
    if plan.placeholder_count:
        if use_en:
            hanging = f"hanging {plan.placeholder_count} for now. What should they be called?"
        else:
            hanging = f"先挂上{_ZH_COUNT_WORD.get(plan.placeholder_count, str(plan.placeholder_count))}条。叫什么？"
        bits.append(hanging)
    elif adds:
        quoted = "".join(_quote(label, lang) for label in adds if label)
        bits.append(f"adding {quoted}" if use_en else f"加上{quoted}")
    joiner = ", " if use_en else "，"
    detail = joiner.join(bit for bit in bits if bit)
    if use_en and not detail.endswith("?"):
        return f"{detail}."
    if not use_en and not detail.endswith("？") and not detail.endswith("。"):
        return f"{detail}。"
    return detail


async def _arm_placeholder_slot(
    voice_session_id: str,
    created: List[str],
    *,
    lang: str,
) -> None:
    ids = [item for item in created if item]
    if not ids:
        return
    live = voice_sessions.get(voice_session_id)
    if not isinstance(live, dict):
        return
    followup = "What should they be called?" if lang == "en" else "叫什么？"
    armed = arm_pending_intent_slot(
        live,
        {"slot_action": "update_node", "node_ids": ids, "followup": followup},
    )
    if armed:
        await persist_armed_intent_slot(live)


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
