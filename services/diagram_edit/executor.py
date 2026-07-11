"""Diagram Edit Tool executor — validate, dispatch, await verified ack.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.diagram_edit.convert import legacy_command_to_diagram_edit
from services.diagram_edit.effects import build_expected_effect, extract_before_fingerprint
from services.diagram_edit.handlers.mindmap import register_mindmap_handlers
from services.diagram_edit.pending import (
    cache_result,
    get_cached_result,
    new_mutation_id,
    register_pending,
    wait_for_ack,
)
from services.diagram_edit.registry import dispatch_tool
from services.diagram_edit.transport.kitty_ws import KittyWsTransport
from services.diagram_edit.transport.protocol import CanvasTransport
from services.diagram_edit.types import (
    MINDMAP_DIAGRAM_TYPES,
    STRUCTURAL_TOOLS,
    DiagramEditCommand,
    ErrorCode,
    ToolResult,
    VerificationReport,
    coerce_error_code,
)
from services.diagram_edit.verify import extract_created_node_id, verify_effect_on_snapshot
from services.kitty.infra.scope.kitty_scope_access import user_may_access_kitty_scope

logger = logging.getLogger(__name__)

_DEFAULT_ACK_TIMEOUT_SEC = 8.0
"""Must exceed FE hub-persist wait (3s) plus apply/verify/RTT so client can ack."""


class _HandlerBootstrap:
    """One-shot handler registration holder."""

    done: bool = False


def _ensure_handlers() -> None:
    if _HandlerBootstrap.done:
        return
    register_mindmap_handlers()
    _HandlerBootstrap.done = True


def _normalize_diagram_type(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "mindmap"
    val = raw.strip().lower()
    if val == "mind_map":
        return "mindmap"
    return val


def _write_lock_busy(session_context: Dict[str, Any]) -> bool:
    lock_raw = session_context.get("diagram_write_lock")
    if not isinstance(lock_raw, dict):
        return False
    holder = lock_raw.get("holder")
    return holder == "llm"


def _rejected(
    mutation_id: str,
    error_code: ErrorCode,
    message: Optional[str] = None,
) -> ToolResult:
    return ToolResult(
        status="rejected",
        mutation_id=mutation_id,
        error_code=error_code,
        message=message,
    )


def _failed(
    mutation_id: str,
    error_code: ErrorCode,
    message: Optional[str] = None,
    verification: Optional[VerificationReport] = None,
) -> ToolResult:
    return ToolResult(
        status="failed",
        mutation_id=mutation_id,
        error_code=error_code,
        message=message,
        verification=verification,
    )


async def execute_diagram_edit(
    websocket: WebSocket,
    voice_session_id: str,
    command: DiagramEditCommand,
    session_context: Dict[str, Any],
    *,
    user_id: Optional[int] = None,
    ack_timeout_sec: float = _DEFAULT_ACK_TIMEOUT_SEC,
    transport: Optional[CanvasTransport] = None,
    verify_required: bool = True,
    require_hub_persist: bool = False,
) -> ToolResult:
    """
    Execute a diagram edit with mandatory post-apply verification.

    ``applied`` only when the owning canvas acks verified (and hub persist when required).
    """
    _ensure_handlers()

    canvas_transport: CanvasTransport = transport or KittyWsTransport()
    mutation_id = new_mutation_id()
    diagram_type = _normalize_diagram_type(command.diagram_type)

    if command.idempotency_key:
        cached = get_cached_result(command.idempotency_key)
        if cached is not None:
            return cached

    if command.tool not in STRUCTURAL_TOOLS:
        return _rejected(mutation_id, "unsupported_tool", f"Unknown tool: {command.tool}")

    if diagram_type not in MINDMAP_DIAGRAM_TYPES:
        return _rejected(mutation_id, "unsupported_diagram_type")

    if user_id is not None:
        allowed = await user_may_access_kitty_scope(user_id, command.scope)
        if not allowed:
            return _rejected(mutation_id, "access_denied")

    live = canvas_transport.get_live_session(voice_session_id)
    if live is None:
        return _rejected(mutation_id, "no_owner", "No bound voice session")

    if _write_lock_busy(session_context):
        return _rejected(mutation_id, "busy_llm_generating")

    hub_rev = canvas_transport.get_hub_revision(voice_session_id)
    if command.expected_revision is not None and hub_rev is not None:
        if int(command.expected_revision) != int(hub_rev):
            return _rejected(mutation_id, "stale_revision")

    if verify_required and command.tool == "diagram.add_node":
        text_raw = command.args.get("text")
        legacy = command.legacy_command if isinstance(command.legacy_command, dict) else {}
        legacy_target = legacy.get("target")
        has_text = (isinstance(text_raw, str) and text_raw.strip()) or (
            isinstance(legacy_target, str) and legacy_target.strip()
        )
        if not has_text:
            return _rejected(
                mutation_id,
                "not_parsed",
                "add_node requires non-empty target text",
            )

    before_fp = extract_before_fingerprint(session_context)
    before_nodes = before_fp.get("nodes")
    before_count = len(before_nodes) if isinstance(before_nodes, list) else None

    effect = build_expected_effect(command, before_fp)

    register_pending(
        mutation_id,
        voice_session_id,
        idempotency_key=command.idempotency_key,
    )

    outbound_extras = {
        "mutation_id": mutation_id,
        "expected_effect": effect.to_dict(),
        "before_fingerprint": before_fp,
    }
    session_context["_diagram_edit_outbound_extras"] = outbound_extras
    canvas_transport.stash_outbound_extras(voice_session_id, outbound_extras)

    executed = await dispatch_tool(
        websocket,
        voice_session_id,
        command,
        session_context,
    )
    session_context.pop("_diagram_edit_outbound_extras", None)
    canvas_transport.pop_outbound_extras(voice_session_id)

    if not executed:
        return _failed(mutation_id, "apply_noop", "Dispatch returned without apply")

    if not verify_required:
        applied_ops = [{"op": effect.op, "text": effect.text}]
        result = ToolResult(
            status="applied",
            mutation_id=mutation_id,
            revision=hub_rev,
            applied_ops=applied_ops,
        )
        if command.idempotency_key:
            cache_result(command.idempotency_key, result)
        return result

    ack = await wait_for_ack(mutation_id, timeout_sec=ack_timeout_sec)
    if ack is None:
        result = _failed(mutation_id, "ack_timeout", "Owning canvas did not ack in time")
        if command.idempotency_key:
            cache_result(command.idempotency_key, result)
        return result

    if not ack.verified:
        err = coerce_error_code(ack.error_code, "verify_failed")
        result = _failed(
            mutation_id,
            err,
            ack.message or "Canvas verification failed",
        )
        if command.idempotency_key:
            cache_result(command.idempotency_key, result)
        return result

    if require_hub_persist and ack.hub_persist_ok is not True:
        err = coerce_error_code(ack.error_code, "hub_persist_failed")
        result = _failed(
            mutation_id,
            err,
            ack.message or "Hub persist failed after canvas verify",
        )
        if command.idempotency_key:
            cache_result(command.idempotency_key, result)
        return result

    evidence = ack.evidence if isinstance(ack.evidence, dict) else {}
    server_verify = verify_effect_on_snapshot(
        effect,
        evidence,
        before_node_count=before_count,
        diagram_type=diagram_type,
    )
    if not server_verify.ok:
        result = _failed(
            mutation_id,
            "verify_failed",
            server_verify.error or "Server re-check failed",
            verification=server_verify,
        )
        if command.idempotency_key:
            cache_result(command.idempotency_key, result)
        return result

    new_rev = ack.hub_revision if ack.hub_revision is not None else ack.revision
    if new_rev is not None:
        canvas_transport.set_hub_revision(voice_session_id, int(new_rev))

    created_id = extract_created_node_id(
        effect,
        evidence,
        created_node_ids=ack.created_node_ids,
    )
    applied_op: Dict[str, Any] = {"op": effect.op, "text": effect.text}
    if created_id:
        applied_op["node_id"] = created_id
    applied_ops = [applied_op]
    result = ToolResult(
        status="applied",
        mutation_id=mutation_id,
        revision=new_rev,
        applied_ops=applied_ops,
        verification=server_verify,
    )
    if command.idempotency_key:
        cache_result(command.idempotency_key, result)
    return result


async def execute_diagram_edit_from_legacy(
    websocket: WebSocket,
    voice_session_id: str,
    legacy_command: Dict[str, Any],
    session_context: Dict[str, Any],
    *,
    scope: str,
    diagram_type: str,
    user_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
    source_agent: str = "kitty",
    ack_timeout_sec: float = _DEFAULT_ACK_TIMEOUT_SEC,
    transport: Optional[CanvasTransport] = None,
    verify_required: bool = True,
    require_hub_persist: bool = False,
) -> ToolResult:
    """Convenience entry from legacy Kitty command dict."""
    canvas_transport: CanvasTransport = transport or KittyWsTransport()
    expected_revision = canvas_transport.get_hub_revision(voice_session_id)

    cmd = legacy_command_to_diagram_edit(
        legacy_command,
        scope=scope,
        diagram_type=diagram_type,
        expected_revision=expected_revision,
        idempotency_key=idempotency_key,
        source_agent=source_agent,
    )
    if cmd is None:
        return _failed(new_mutation_id(), "not_parsed", "Could not map legacy command")

    return await execute_diagram_edit(
        websocket,
        voice_session_id,
        cmd,
        session_context,
        user_id=user_id,
        ack_timeout_sec=ack_timeout_sec,
        transport=canvas_transport,
        verify_required=verify_required,
        require_hub_persist=require_hub_persist,
    )
