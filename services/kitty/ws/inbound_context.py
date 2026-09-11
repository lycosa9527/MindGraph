"""Kitty inbound handlers for context_update, pairing snapshot, and mutation ack.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from services.agent_hub import build_desktop_pairing_snapshot, get_mind_graph_agent_hub
from services.diagram_edit.ack import complete_mutation_ack_from_client
from services.kitty.context.hub_context import apply_kitty_ws_context_patch
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.bootstrap.kitty_context_hydrate import (
    diagram_data_has_visible_content,
    merge_voice_context_with_library,
)
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    kitty_llm_model_update_from_context,
    publish_kitty_llm_model_update,
    publish_kitty_selection_update,
)
from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.session.events import KittyEvent, get_session_event_bus
from services.kitty.session.manager import get_kitty_session_manager
from services.kitty.session.ops import get_agent_session_id, update_panel_context
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.ws.inbound_types import KittyInboundFlow, KittyWsInboundContext

logger = logging.getLogger(__name__)


async def handle_get_desktop_session_snapshot(
    ctx: KittyWsInboundContext,
    _message: dict,
) -> KittyInboundFlow:
    """Return the pairing snapshot for the current diagram scope."""
    lane = voice_sessions[ctx.voice_session_id].get("_kitty_client_lane")
    snapshot_payload = await build_desktop_pairing_snapshot(
        int(ctx.current_user.id),
        ctx.diagram_session_id,
        client_lane=lane if isinstance(lane, str) else None,
    )
    await safe_websocket_send(
        ctx.websocket,
        {
            "type": "desktop_session_snapshot",
            "snapshot": snapshot_payload,
        },
    )
    return "continue"


async def handle_diagram_mutation_ack(
    ctx: KittyWsInboundContext,
    message: dict,
) -> KittyInboundFlow:
    """Complete a pending verified mutation and journal the ack."""
    matched = complete_mutation_ack_from_client(message)
    mid_raw = message.get("mutation_id")
    mid = mid_raw.strip() if isinstance(mid_raw, str) and mid_raw.strip() else None
    sess = voice_sessions.get(ctx.voice_session_id)
    if mid and isinstance(sess, dict):
        req_raw = sess.get("_one_sentence_request_id")
        req_id = req_raw.strip() if isinstance(req_raw, str) and req_raw.strip() else None
        lane_raw = sess.get("_kitty_client_lane")
        lane = lane_raw.strip() if isinstance(lane_raw, str) and lane_raw.strip() else None
        verified = message.get("verified") is True or message.get("ok") is True
        await get_kitty_session_manager().link_mutation(
            user_id=int(ctx.current_user.id),
            scope=ctx.diagram_session_id,
            mutation_id=mid,
            request_id=req_id,
            voice_session_id=ctx.voice_session_id,
            lane=lane,
            outcome="ack",
            detail={"matched": matched, "verified": verified},
        )
    kitty_wf_log(
        "diagram_ack",
        "matched" if matched else "orphan",
        voice_session_id=ctx.voice_session_id,
    )
    return "continue"


async def _send_context_fail(
    ctx: KittyWsInboundContext,
    *,
    error: str,
    idempotency_key: str | None,
    persist_library: bool,
) -> KittyInboundFlow:
    kitty_wf_log(
        "hub_context_fail",
        error[:120],
        voice_session_id=ctx.voice_session_id,
        scope=ctx.diagram_session_id,
    )
    await safe_websocket_send(
        ctx.websocket,
        {
            "type": "context_mutation_ack",
            "ok": False,
            "error": error,
            "idempotency_key": idempotency_key,
            "persist_library": persist_library,
        },
    )
    return "continue"


async def handle_context_update(
    ctx: KittyWsInboundContext,
    message: dict,
) -> KittyInboundFlow:
    """Merge client context, persist hub live_spec, and ack the mutation."""
    websocket = ctx.websocket
    voice_session_id = ctx.voice_session_id
    diagram_session_id = ctx.diagram_session_id
    new_context_in = message.get("context", {}) or {}
    cur_panel = voice_sessions[voice_session_id].get("active_panel", "none")
    active_panel = message.get("active_panel") or new_context_in.get("active_panel") or cur_panel or "none"
    session_dt = (
        voice_sessions[voice_session_id].get("diagram_type") or new_context_in.get("diagram_type") or "circle_map"
    )
    client_lane = voice_sessions[voice_session_id].get("_kitty_client_lane")
    delta_dd_raw = new_context_in.get("diagram_data")
    delta_dd: dict[str, Any] = delta_dd_raw if isinstance(delta_dd_raw, dict) else {}
    lib_raw = new_context_in.get("diagram_library_id")
    prefer_server = bool(
        client_lane == "mobile"
        and isinstance(lib_raw, str)
        and lib_raw.strip()
        and not diagram_data_has_visible_content(delta_dd)
    )
    merged_ctx, res_dt, res_panel = await merge_voice_context_with_library(
        ctx.current_user.id,
        new_context_in,
        diagram_type=session_dt,
        active_panel=active_panel,
        prefer_server_diagram_nodes=prefer_server,
    )
    new_diagram_type = res_dt

    old_diagram_type = voice_sessions[voice_session_id].get("diagram_type")
    voice_sessions[voice_session_id]["diagram_type"] = new_diagram_type
    if old_diagram_type != new_diagram_type:
        logger.info(
            "VOIC | Diagram type updated: %s -> %s for session %s",
            old_diagram_type,
            new_diagram_type,
            voice_session_id,
        )

    update_panel_context(voice_session_id, res_panel)
    voice_sessions[voice_session_id]["context"] = copy.deepcopy(merged_ctx)
    voice_sessions[voice_session_id]["context"]["diagram_type"] = new_diagram_type

    agent_session_id_mu = get_agent_session_id(voice_session_id)
    agent = kitty_agent_manager.get_or_create(agent_session_id_mu)
    diagram_data = dict(merged_ctx.get("diagram_data", {}))
    diagram_data["diagram_type"] = new_diagram_type
    agent.update_diagram_state(diagram_data)
    agent.update_panel_state(res_panel, merged_ctx.get("panels", {}))

    ctx_reason = "diagram_type_change" if old_diagram_type != new_diagram_type else "context_update"
    bus = get_session_event_bus(voice_session_id)
    await bus.emit(
        KittyEvent(
            kind="context_update",
            voice_session_id=voice_session_id,
            payload={"diagram_type": new_diagram_type, "reason": ctx_reason},
        )
    )

    hub_rev_raw = voice_sessions[voice_session_id].get("_hub_scope_revision")
    hub_rev = hub_rev_raw if isinstance(hub_rev_raw, int) else None
    client_rev_raw = message.get("expected_revision")
    if isinstance(client_rev_raw, int):
        hub_rev = client_rev_raw
    elif isinstance(client_rev_raw, (float, str)):
        try:
            hub_rev = int(client_rev_raw)
        except (TypeError, ValueError):
            pass
    idempotency_key_raw = message.get("idempotency_key")
    idempotency_key = (
        str(idempotency_key_raw).strip()
        if isinstance(idempotency_key_raw, str) and idempotency_key_raw.strip()
        else None
    )
    persist_library = message.get("persist_library") is True
    library_snapshot_raw = message.get("library_snapshot")
    library_snapshot = library_snapshot_raw if isinstance(library_snapshot_raw, dict) else None
    try:
        mutation_out = await apply_kitty_ws_context_patch(
            ctx.hub,
            hub_session_id=ctx.hub_session_id,
            diagram_scope=diagram_session_id,
            merged_context=merged_ctx,
            diagram_type=new_diagram_type,
            active_panel=res_panel,
            expected_revision=hub_rev,
            idempotency_key=idempotency_key,
            persist_library=persist_library,
            library_snapshot=library_snapshot,
        )
    except ValueError as mut_err:
        if "stale expected revision" not in str(mut_err).lower():
            logger.warning("Hub mutation rejected for %s: %s", voice_session_id, mut_err)
            return await _send_context_fail(
                ctx,
                error=str(mut_err),
                idempotency_key=idempotency_key,
                persist_library=persist_library,
            )
        fresh_rev = get_mind_graph_agent_hub().get_binding_revision(ctx.hub_session_id)
        if fresh_rev is None:
            logger.warning("Hub mutation rejected for %s: %s", voice_session_id, mut_err)
            return await _send_context_fail(
                ctx,
                error=str(mut_err),
                idempotency_key=idempotency_key,
                persist_library=persist_library,
            )
        try:
            mutation_out = await apply_kitty_ws_context_patch(
                ctx.hub,
                hub_session_id=ctx.hub_session_id,
                diagram_scope=diagram_session_id,
                merged_context=merged_ctx,
                diagram_type=new_diagram_type,
                active_panel=res_panel,
                expected_revision=fresh_rev,
                idempotency_key=(f"{idempotency_key}-retry" if idempotency_key else None),
                persist_library=persist_library,
                library_snapshot=library_snapshot,
            )
        except ValueError as retry_err:
            logger.warning(
                "Hub mutation retry rejected for %s: %s",
                voice_session_id,
                retry_err,
            )
            return await _send_context_fail(
                ctx,
                error=str(retry_err),
                idempotency_key=idempotency_key,
                persist_library=persist_library,
            )

    new_rev = mutation_out.get("revision")
    if isinstance(new_rev, int):
        voice_sessions[voice_session_id]["_hub_scope_revision"] = new_rev
    live_ts = mutation_out.get("live_spec_updated_at")
    if isinstance(live_ts, int) and live_ts > 0:
        voice_sessions[voice_session_id]["_kitty_redis_seen_ts"] = live_ts

    nodes_raw = diagram_data.get("nodes")
    nodes_count = len(nodes_raw) if isinstance(nodes_raw, list) else 0
    children_count = len(diagram_data.get("children", []))

    kitty_wf_log(
        "hub_context",
        f"ack ok rev={new_rev} persist={persist_library} nodes={nodes_count or children_count}",
        voice_session_id=voice_session_id,
        scope=diagram_session_id,
    )

    await safe_websocket_send(
        websocket,
        {
            "type": "context_mutation_ack",
            "ok": True,
            "revision": new_rev,
            "library_snapshot_saved": mutation_out.get("library_snapshot_saved"),
            "library_snapshot_error": mutation_out.get("library_snapshot_error"),
            "idempotency_key": idempotency_key,
            "persist_library": persist_library,
        },
    )

    logger.debug(
        "Context updated for %s with %d nodes",
        voice_session_id,
        nodes_count or children_count,
    )
    sel_raw = merged_ctx.get("selected_nodes")
    selected_nodes: list[str] = []
    if isinstance(sel_raw, list):
        for item in sel_raw:
            if isinstance(item, str) and item.strip():
                selected_nodes.append(item.strip())
    if selected_nodes:
        await publish_kitty_selection_update(
            int(ctx.current_user.id),
            diagram_session_id,
            selected_nodes,
        )
    should_llm, llm_model = kitty_llm_model_update_from_context(merged_ctx)
    if should_llm:
        await publish_kitty_llm_model_update(
            int(ctx.current_user.id),
            diagram_session_id,
            llm_model,
        )
    return "continue"
