"""Sequential structural mutation chain for multi-edit one-sentence turns.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket

from services.diagram_edit.transport.kitty_ws import MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY
from services.kitty.ack.ack_failure import render_failure_ack_for_command
from services.kitty.ack.ack_library import render_ack
from services.kitty.ack.ack_slots import enrich_ack_session_context
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.routing.one_sentence_edit_helpers import CLIENT_REPORTED_FAILURE_CODES
from services.kitty.routing.node_action_order import order_node_action_commands
from services.kitty.routing.pending_branch_autocomplete import (
    created_node_id_from_applied_ops,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.runtime_state import logger, voice_sessions

STRUCTURAL_CHAIN_ACTIONS = frozenset(
    {
        "update_center",
        "add_node",
        "update_node",
        "delete_node",
    }
)


def split_structural_follow_ups(
    follow_ups: list[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """Split follow-ups into structural mutations vs autocomplete / other."""
    structural: list[Dict[str, Any]] = []
    rest: list[Dict[str, Any]] = []
    for item in follow_ups:
        action = str(item.get("action") or "").strip()
        if action in STRUCTURAL_CHAIN_ACTIONS:
            structural.append(dict(item))
        else:
            rest.append(dict(item))
    return structural, rest


def build_structural_steps(
    primary_command: Dict[str, Any],
    structural_follow_ups: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """Primary (sans follow_ups) plus structural follow-ups, in order."""
    primary = dict(primary_command)
    primary.pop("follow_up_actions", None)
    steps = [primary]
    for follow in structural_follow_ups:
        steps.append(dict(follow))
    return steps


def is_multi_structural_turn(structural_follow_ups: list[Dict[str, Any]]) -> bool:
    """True when more than one structural mutation will run in this turn."""
    return bool(structural_follow_ups)


def branch_label_from_command(command: Dict[str, Any]) -> str:
    """Best-effort label for an add_node / branch step."""
    for key in ("target", "text", "node_label"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def collect_created_branch(
    command: Dict[str, Any],
    applied_ops: Any,
) -> Optional[Dict[str, str]]:
    """Return ``{label, node_id}`` when an add_node created a canvas node."""
    if str(command.get("action") or "").strip() != "add_node":
        return None
    label = branch_label_from_command(command)
    node_id = created_node_id_from_applied_ops(applied_ops) or ""
    if not label and not node_id:
        return None
    out: Dict[str, str] = {}
    if label:
        out["label"] = label
    if node_id:
        out["node_id"] = node_id
    return out


def _planned_mutations(
    steps: list[Dict[str, Any]],
    *,
    center_topic: str = "",
) -> tuple[str, list[str], list[str], list[str]]:
    """Extract topic / add / rename / delete labels from structural steps."""
    topic = center_topic.strip() if center_topic else ""
    added: list[str] = []
    updated: list[str] = []
    deleted: list[str] = []
    for step in steps:
        action = str(step.get("action") or "").strip()
        label = branch_label_from_command(step)
        if action == "update_center" and label:
            topic = label
        elif action == "add_node" and label:
            added.append(label)
        elif action == "update_node" and label:
            updated.append(label)
        elif action == "delete_node" and label:
            deleted.append(label)
    return topic, added, updated, deleted


# Name branches in chat when the list stays short enough to read aloud.
_NAMED_LABEL_CAP = 8


def _join_en_phrases(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _quote_labels(labels: list[str], *, lang: str) -> str:
    """Readable quoted label list: 「A」、「B」 / "A", "B", and "C"."""
    if lang == "en":
        quoted = [f'"{label}"' for label in labels]
        return _join_en_phrases(quoted)
    return "、".join(f"「{label}」" for label in labels)


def _named_or_count(
    labels: list[str],
    *,
    lang: str,
    named_en: str,
    named_zh: str,
    count_en: str,
    count_zh: str,
) -> str:
    """Prefer naming labels; fall back to a count when the list is long."""
    count = len(labels)
    if count <= _NAMED_LABEL_CAP:
        named = _quote_labels(labels, lang=lang)
        return named_en.format(labels=named) if lang == "en" else named_zh.format(labels=named)
    return count_en.format(count=count) if lang == "en" else count_zh.format(count=count)


def _clause_list(parts: list[str], *, lang: str) -> str:
    if not parts:
        return ""
    if lang == "en":
        return _join_en_phrases(parts)
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}，并" + "，".join(parts[1:])


def _progress_detail(
    *,
    lang: str,
    topic: str,
    branch_labels: list[str],
    updated_labels: list[str] | None = None,
    deleted_labels: list[str] | None = None,
) -> str:
    """Natural progress clause (no trailing ellipsis — template adds it)."""
    updated = list(updated_labels or [])
    deleted = list(deleted_labels or [])
    parts: list[str] = []
    if lang == "en":
        if topic:
            parts.append(f'updating the topic to "{topic}"')
        if branch_labels:
            parts.append(
                _named_or_count(
                    branch_labels,
                    lang=lang,
                    named_en="adding {labels}",
                    named_zh="",
                    count_en="adding {count} branches",
                    count_zh="",
                )
            )
        if updated:
            parts.append(
                _named_or_count(
                    updated,
                    lang=lang,
                    named_en="renaming {labels}",
                    named_zh="",
                    count_en="renaming {count} nodes",
                    count_zh="",
                )
            )
        if deleted:
            parts.append(
                _named_or_count(
                    deleted,
                    lang=lang,
                    named_en="removing {labels}",
                    named_zh="",
                    count_en="removing {count} nodes",
                    count_zh="",
                )
            )
        return _clause_list(parts, lang=lang) or "applying your changes"
    if topic:
        parts.append(f"正在把主题改为「{topic}」")
    if branch_labels:
        parts.append(
            _named_or_count(
                branch_labels,
                lang=lang,
                named_en="",
                named_zh="添加{labels}",
                count_en="",
                count_zh="添加{count}个分支",
            )
        )
    if updated:
        parts.append(
            _named_or_count(
                updated,
                lang=lang,
                named_en="",
                named_zh="把{labels}改名",
                count_en="",
                count_zh="修改{count}个节点",
            )
        )
    if deleted:
        parts.append(
            _named_or_count(
                deleted,
                lang=lang,
                named_en="",
                named_zh="删除{labels}",
                count_en="",
                count_zh="删除{count}个节点",
            )
        )
    if not parts:
        return "正在处理你的修改"
    if not topic and not parts[0].startswith("正在"):
        parts[0] = f"正在{parts[0]}"
    return _clause_list(parts, lang=lang)


def _done_core(
    *,
    lang: str,
    topic: str,
    branch_labels: list[str],
    updated_labels: list[str] | None = None,
    deleted_labels: list[str] | None = None,
) -> str:
    """Core done sentence without trailing complete clause."""
    updated = list(updated_labels or [])
    deleted = list(deleted_labels or [])
    parts: list[str] = []
    if lang == "en":
        if topic:
            parts.append(f'Topic set to "{topic}"')
        if branch_labels:
            # "A, B, C, and D are ready" — clear confirmation of what landed.
            ready_named = "{labels} is ready" if len(branch_labels) == 1 else "{labels} are ready"
            parts.append(
                _named_or_count(
                    branch_labels,
                    lang=lang,
                    named_en=ready_named,
                    named_zh="",
                    count_en="{count} branches are ready",
                    count_zh="",
                )
            )
        if updated:
            parts.append(
                _named_or_count(
                    updated,
                    lang=lang,
                    named_en="renamed {labels}",
                    named_zh="",
                    count_en="renamed {count} nodes",
                    count_zh="",
                )
            )
        if deleted:
            parts.append(
                _named_or_count(
                    deleted,
                    lang=lang,
                    named_en="removed {labels}",
                    named_zh="",
                    count_en="removed {count} nodes",
                    count_zh="",
                )
            )
        return _clause_list(parts, lang=lang) or "All set"
    if topic:
        parts.append(f"主题已改为「{topic}」")
    if branch_labels:
        parts.append(
            _named_or_count(
                branch_labels,
                lang=lang,
                named_en="",
                named_zh="{labels}已经加好了",
                count_en="",
                count_zh="{count}个分支已经加好了",
            )
        )
    if updated:
        parts.append(
            _named_or_count(
                updated,
                lang=lang,
                named_en="",
                named_zh="已改名{labels}",
                count_en="",
                count_zh="已改名{count}个节点",
            )
        )
    if deleted:
        parts.append(
            _named_or_count(
                deleted,
                lang=lang,
                named_en="",
                named_zh="已删除{labels}",
                count_en="",
                count_zh="已删除{count}个节点",
            )
        )
    if not parts:
        return "改好了"
    # Done clauses are already full units — join with commas, not 「并」.
    return "，".join(parts)


def render_multi_step_progress(
    *,
    lang: str,
    topic: str = "",
    branch_labels: list[str] | None = None,
    updated_labels: list[str] | None = None,
    deleted_labels: list[str] | None = None,
) -> str:
    """Single progress line for a multi-mutation turn."""
    detail = _progress_detail(
        lang=lang,
        topic=topic.strip() if topic else "",
        branch_labels=list(branch_labels or []),
        updated_labels=list(updated_labels or []),
        deleted_labels=list(deleted_labels or []),
    )
    return render_ack("diagram.multi_step.progress", {"detail": detail}, lang=lang)


def render_multi_step_done(
    *,
    lang: str,
    topic: str,
    branch_labels: list[str],
    completing: bool,
    updated_labels: list[str] | None = None,
    deleted_labels: list[str] | None = None,
) -> str:
    """Single summary done line listing topic / branches / renames / deletes."""
    core = _done_core(
        lang=lang,
        topic=topic.strip() if topic else "",
        branch_labels=list(branch_labels),
        updated_labels=list(updated_labels or []),
        deleted_labels=list(deleted_labels or []),
    )
    if completing:
        # Templates append the fill clause after ``detail``.
        detail = f"{core}. " if lang == "en" else f"{core}，"
        return render_ack(
            "diagram.multi_step.done_with_complete",
            {"detail": detail},
            lang=lang,
        )
    detail = f"{core}." if lang == "en" else f"{core}。"
    return render_ack("diagram.multi_step.done", {"detail": detail}, lang=lang)


def peel_chain_from_command(
    command: Dict[str, Any],
    follow_up_actions: list[Dict[str, Any]],
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]], bool]:
    """
    Return (structural_steps, autocomplete_follow_ups, is_multi).

    ``structural_steps`` always includes the primary command, re-ordered by
    the canonical node-action ladder (topic/delete/update before adds).
    """
    structural_follows, autocomplete = split_structural_follow_ups(follow_up_actions)
    steps = order_node_action_commands(build_structural_steps(command, structural_follows))
    autocomplete = order_node_action_commands(autocomplete)
    multi = is_multi_structural_turn(structural_follows)
    return steps, autocomplete, multi


async def emit_deferred_branch_completes(
    router: ModuleType,
    websocket: WebSocket,
    voice_session_id: str,
    created_branches: list[Dict[str, str]],
    *,
    command_text: str,
    lang: str,
) -> int:
    """Fire silent auto_complete_branch for each created branch. Returns emit count."""
    emitted = 0
    for branch in created_branches:
        label = str(branch.get("label") or "").strip()
        node_id = str(branch.get("node_id") or "").strip()
        if not label and not node_id:
            continue
        ok = await router.emit_auto_complete_branch(
            websocket,
            voice_session_id,
            label,
            command_text=command_text,
            lang=lang,
            node_id=node_id or None,
            silent_ack=True,
        )
        if ok:
            emitted += 1
            kitty_wf_log(
                "follow_up",
                f"deferred auto_complete_branch target={label or node_id}",
                voice_session_id=voice_session_id,
                action="auto_complete_branch",
            )
    return emitted


def filter_autocomplete_after_deferred(
    autocomplete_follow_ups: list[Dict[str, Any]],
    *,
    created_branches: list[Dict[str, str]],
    completing: bool,
    voice_session_id: str = "",
) -> list[Dict[str, Any]]:
    """
    Keep leftover autocomplete that still needs to run after deferred fills.

    - Drop ``auto_complete_branch`` for branches created in this chain (already
      covered by deferred silent emits).
    - Keep ``auto_complete_branch`` for other EXISTING targets.
    - Drop whole-map ``auto_complete`` when deferred branch fills ran (would wipe).
    """
    created_labels = {
        str(item.get("label") or "").strip() for item in created_branches if str(item.get("label") or "").strip()
    }
    created_ids = {
        str(item.get("node_id") or "").strip() for item in created_branches if str(item.get("node_id") or "").strip()
    }
    other_follows: list[Dict[str, Any]] = []
    for follow in autocomplete_follow_ups:
        action = str(follow.get("action") or "").strip()
        if action == "auto_complete_branch":
            target = str(follow.get("target") or follow.get("node_label") or "").strip()
            node_id = str(follow.get("node_id") or "").strip()
            if (target and target in created_labels) or (node_id and node_id in created_ids):
                continue
            other_follows.append(dict(follow))
            continue
        if completing and action == "auto_complete":
            logger.info(
                "Skipping whole-map auto_complete after deferred branch completes (voice_session_id=%s)",
                voice_session_id,
            )
            continue
        other_follows.append(dict(follow))
    return other_follows


async def run_verified_structural_chain(
    router: ModuleType,
    websocket: WebSocket,
    voice_session_id: str,
    steps: list[Dict[str, Any]],
    session_context: Dict[str, Any],
    *,
    scope: str,
    diagram_type: str,
    user_id: Optional[int],
    live_session: Optional[Dict[str, Any]],
    command_text: str,
    lang: str,
    autocomplete_follow_ups: list[Dict[str, Any]],
    execute_follow_up_actions: Any,
    center_topic: str,
    verify_required: bool = True,
) -> Any:
    """
    Apply structural steps sequentially with coalesced Kitty chat acks.

    After all adds succeed, emit silent branch auto-completes for created
    branches, then run remaining autocomplete follow-ups that still apply.
    """
    if len(steps) < 2:
        return router.finish_route(
            voice_session_id,
            router.RouteOutcome.FAILED,
            reason="empty_structural_chain",
        )

    live = voice_sessions.get(voice_session_id)
    if isinstance(live, dict):
        live[MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY] = True

    try:
        return await _run_verified_structural_chain_body(
            router,
            websocket,
            voice_session_id,
            steps,
            session_context,
            scope=scope,
            diagram_type=diagram_type,
            user_id=user_id,
            live_session=live_session,
            command_text=command_text,
            lang=lang,
            autocomplete_follow_ups=autocomplete_follow_ups,
            execute_follow_up_actions=execute_follow_up_actions,
            center_topic=center_topic,
            verify_required=verify_required,
        )
    finally:
        if isinstance(live, dict):
            live.pop(MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY, None)


async def _run_verified_structural_chain_body(
    router: ModuleType,
    websocket: WebSocket,
    voice_session_id: str,
    steps: list[Dict[str, Any]],
    session_context: Dict[str, Any],
    *,
    scope: str,
    diagram_type: str,
    user_id: Optional[int],
    live_session: Optional[Dict[str, Any]],
    command_text: str,
    lang: str,
    autocomplete_follow_ups: list[Dict[str, Any]],
    execute_follow_up_actions: Any,
    center_topic: str,
    verify_required: bool = True,
) -> Any:
    """Inner multi-step apply loop (chat suppression managed by caller)."""
    primary_action = str(steps[0].get("action") or "")
    planned_topic, planned_branches, planned_updated, planned_deleted = _planned_mutations(
        steps,
        center_topic=center_topic,
    )
    progress_text = render_multi_step_progress(
        lang=lang,
        topic=planned_topic,
        branch_labels=planned_branches,
        updated_labels=planned_updated,
        deleted_labels=planned_deleted,
    )
    await router.emit_user_ack(
        websocket,
        voice_session_id,
        progress_text,
        one_sentence_action=primary_action or None,
        one_sentence_outcome="pending",
        one_sentence_user_text=command_text,
        reply_kind="progress",
    )

    created_branches: List[Dict[str, str]] = []
    updated_applied: List[str] = []
    deleted_applied: List[str] = []
    topic_applied = planned_topic
    last_action = primary_action

    for step in steps:
        step_action = str(step.get("action") or "").strip()
        last_action = step_action or last_action
        bus_result = await router.apply_kitty_legacy_diagram_command(
            websocket,
            voice_session_id,
            step,
            session_context,
            scope=scope,
            diagram_type=str(diagram_type),
            user_id=user_id,
            verify_required=verify_required,
        )
        tool_result = bus_result.tool_result
        if tool_result.status != "applied":
            err_code = tool_result.error_code or "verify_failed"
            if err_code not in CLIENT_REPORTED_FAILURE_CODES:
                fail_text = render_failure_ack_for_command(
                    step_action,
                    step,
                    enrich_ack_session_context(session_context, live_session),
                    error_code=err_code,
                    lang=lang,
                )
                await router.send_diagram_failure_ack(
                    websocket,
                    voice_session_id,
                    fail_text,
                    one_sentence_action=step_action or None,
                    one_sentence_outcome="failed",
                    one_sentence_user_text=command_text,
                )
            else:
                kitty_wf_log(
                    "diagram_execute",
                    f"{step_action} failed client-reported code={err_code}",
                    voice_session_id=voice_session_id,
                    action=step_action,
                )
            return router.finish_route(
                voice_session_id,
                router.RouteOutcome.FAILED,
                reason=str(err_code),
                action=step_action or None,
            )

        kitty_wf_log(
            "diagram_execute",
            f"{step_action} verified chain-step",
            voice_session_id=voice_session_id,
            action=step_action,
        )
        if step_action == "update_center":
            label = branch_label_from_command(step)
            if label:
                topic_applied = label
        elif step_action == "update_node":
            label = branch_label_from_command(step)
            if label:
                updated_applied.append(label)
        elif step_action == "delete_node":
            label = branch_label_from_command(step)
            if label:
                deleted_applied.append(label)
        created = collect_created_branch(step, tool_result.applied_ops)
        if created:
            created_branches.append(created)

    completing = bool(created_branches)
    ack_text = render_multi_step_done(
        lang=lang,
        topic=topic_applied,
        branch_labels=[b.get("label", "") for b in created_branches if b.get("label")],
        completing=completing,
        updated_labels=updated_applied,
        deleted_labels=deleted_applied,
    )
    await router.emit_user_ack(
        websocket,
        voice_session_id,
        ack_text,
        one_sentence_action=primary_action or None,
        one_sentence_outcome="executed",
        one_sentence_user_text=command_text,
    )
    memory = get_session_memory(voice_session_id)
    memory.append_action_turn(ack_text, action=primary_action or "multi_step")

    if completing:
        await emit_deferred_branch_completes(
            router,
            websocket,
            voice_session_id,
            created_branches,
            command_text=command_text,
            lang=lang,
        )

    other_follows = filter_autocomplete_after_deferred(
        autocomplete_follow_ups,
        created_branches=created_branches,
        completing=completing,
        voice_session_id=voice_session_id,
    )
    if other_follows:
        await execute_follow_up_actions(
            router,
            websocket,
            voice_session_id,
            other_follows,
            session_context=session_context,
            command_text=command_text,
            topic=topic_applied or None,
            silent_branch_ack=True,
        )
    return router.finish_route(
        voice_session_id,
        router.RouteOutcome.EXECUTED,
        action=last_action or None,
    )
