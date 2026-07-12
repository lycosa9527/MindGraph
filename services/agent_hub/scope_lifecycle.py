"""
MindGraph agent orchestration: Kitty voice scope lifecycle (multi-worker).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import WebSocket

from services.diagram_edit.ack import configure_mutation_ack_relay
from services.infrastructure.monitoring.ws_metrics import (
    record_kitty_refcount_attach,
    record_kitty_refcount_attach_failed,
    record_kitty_refcount_detach_failed,
    record_kitty_refcount_detach_mismatch,
    record_kitty_refcount_teardown,
)
from services.kitty.infra.bootstrap.kitty_context_hydrate import (
    diagram_data_has_visible_content,
    merge_voice_context_with_library,
    resolve_mobile_open_bootstrap,
)
from services.kitty.infra.control.kitty_canvas_owner_relay import publish_mutation_ack_relay
from services.kitty.infra.control.kitty_control_fanout import (
    KITTY_CONTROL_REASON_HANDSHAKE_PREEMPT,
    KITTY_CONTROL_REASON_IDLE_TIMEOUT,
    configure_kitty_control_dispatch,
    publish_kitty_close_scope_async,
)
from services.kitty.infra.control.kitty_observability import kitty_extra
from services.kitty.infra.redis.kitty_scope_refcount import (
    KittyDetachResult,
    kitty_scope_refcount_attach,
    kitty_scope_refcount_detach,
)
from services.kitty.infra.redis.kitty_session_redis import (
    upsert_kitty_redis_session,
)
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.redis.cache.redis_diagram_cache import get_diagram_cache

logger = logging.getLogger(__name__)


class _ScopeLifecycleState:
    """Process-wide Kitty scope lifecycle singleton holder."""

    kitty_scope_cleanup: Optional[Callable[[str], Awaitable[bool]]] = None
    active_websockets: Optional[Dict[str, List[WebSocket]]] = None
    voice_sessions: Optional[Dict[str, Any]] = None
    default_hub: Optional["MindGraphAgentHub"] = None


def _new_hub_request_id() -> str:
    """New hub request id."""
    return f"hubreq_{uuid4().hex[:16]}"


def _new_hub_mutation_id() -> str:
    """New hub mutation id."""
    return f"hubmut_{uuid4().hex[:16]}"


@dataclass(slots=True)
class HubTraceState:
    """HubTraceState helper."""

    request_id: str
    mutation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    parent_mutation_id: Optional[str] = None


@dataclass(slots=True)
class HubScopeBinding:
    """HubScopeBinding helper."""

    scope: str
    revision: int = 0
    bound_at: float = field(default_factory=time.time)
    last_mutation_id: Optional[str] = None


@dataclass(slots=True)
class HubKittyRuntimeState:
    """HubKittyRuntimeState helper."""

    voice_session_id: Optional[str] = None
    agent_session_id: Optional[str] = None
    connected: bool = False


@dataclass(slots=True)
class HubSessionState:
    """HubSessionState helper."""

    session_id: str
    user_id: int
    client_lane: Optional[str]
    source_module: str
    connected_at: float
    closed_at: Optional[float] = None
    binding: Optional[HubScopeBinding] = None
    kitty_runtime: HubKittyRuntimeState = field(default_factory=HubKittyRuntimeState)
    trace: HubTraceState = field(default_factory=lambda: HubTraceState(request_id=_new_hub_request_id()))


MutationOp = Literal["replace_context", "patch_context"]


def configure_kitty_scope_cleanup(
    cleanup_voice_by_diagram: Callable[[str], Awaitable[bool]],
) -> None:
    """Inject voice session cleanup (closes local WS + ends Omni sessions)."""
    _ScopeLifecycleState.kitty_scope_cleanup = cleanup_voice_by_diagram
    configure_kitty_control_dispatch(kitty_scope_cleanup=cleanup_voice_by_diagram)


def configure_kitty_control_state(
    active_websockets: Dict[str, List[WebSocket]],
    voice_sessions: Dict[str, Any],
) -> None:
    """Inject process-local registries for control-message fan-in matching."""
    _ScopeLifecycleState.active_websockets = active_websockets
    _ScopeLifecycleState.voice_sessions = voice_sessions
    configure_kitty_control_dispatch(
        active_websockets=active_websockets,
        voice_sessions=voice_sessions,
    )
    configure_mutation_ack_relay(publish=publish_mutation_ack_relay)


def get_mind_graph_agent_hub() -> "MindGraphAgentHub":
    """Singleton façade for routes."""
    if _ScopeLifecycleState.default_hub is None:
        _ScopeLifecycleState.default_hub = MindGraphAgentHub()
    return _ScopeLifecycleState.default_hub


class MindGraphAgentHub:
    """Policy owner for Kitty voice scope: refcount, preempt, HTTP cleanup, mobile diagram bootstrap."""

    def __init__(self) -> None:
        """init  ."""
        self._sessions: Dict[str, HubSessionState] = {}
        self._idempotent_mutation_result: Dict[str, Dict[str, Any]] = {}
        self._session_lock = None

    @property
    def session_lock(self):
        """Session lock."""
        if self._session_lock is None:
            self._session_lock = asyncio.Lock()
        return self._session_lock

    async def open_session(
        self,
        user_id: int,
        *,
        client_lane: Optional[str],
        source_module: str,
    ) -> str:
        """Open session."""
        session_id = f"hubsess_{uuid4().hex[:16]}"
        session = HubSessionState(
            session_id=session_id,
            user_id=int(user_id),
            client_lane=client_lane,
            source_module=source_module,
            connected_at=time.time(),
        )
        async with self.session_lock:
            self._sessions[session_id] = session
        return session_id

    async def close_session(self, hub_session_id: str, *, reason: str) -> None:
        """Close session."""
        async with self.session_lock:
            sess = self._sessions.pop(hub_session_id, None)
        if sess is None:
            return
        sess.closed_at = time.time()
        logger.info(
            "[AgentHub] close_session id=%s user_id=%s reason=%s",
            hub_session_id,
            sess.user_id,
            reason,
            extra=kitty_extra("hub_session_closed", user_id=sess.user_id, reason=reason),
        )

    async def bind_scope(
        self,
        hub_session_id: str,
        *,
        diagram_scope: str,
        source_module: str,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Bind scope."""
        scope = normalize_kitty_diagram_session_id(diagram_scope)
        if scope is None:
            raise ValueError("invalid diagram scope")
        async with self.session_lock:
            sess = self._sessions.get(hub_session_id)
            if sess is None:
                raise ValueError("hub session not found")
            if expected_revision is not None and sess.binding is not None:
                if int(expected_revision) != int(sess.binding.revision):
                    raise ValueError("stale expected revision")
            if sess.binding is None or sess.binding.scope != scope:
                sess.binding = HubScopeBinding(scope=scope, revision=0)
            sess.source_module = source_module
            return {
                "session_id": hub_session_id,
                "scope": sess.binding.scope,
                "revision": sess.binding.revision,
            }

    def get_binding_revision(self, hub_session_id: str) -> Optional[int]:
        """Return current scope revision for a hub session, or None if unbound."""
        sess = self._sessions.get(hub_session_id)
        if sess is None or sess.binding is None:
            return None
        return int(sess.binding.revision)

    async def switch_scope(
        self,
        hub_session_id: str,
        *,
        from_scope: Optional[str],
        to_scope: str,
        source_module: str,
        expected_revision: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Switch scope."""
        if idempotency_key and idempotency_key in self._idempotent_mutation_result:
            return self._idempotent_mutation_result[idempotency_key]
        result = await self.bind_scope(
            hub_session_id,
            diagram_scope=to_scope,
            source_module=source_module,
            expected_revision=expected_revision,
        )
        result["from_scope"] = from_scope
        result["to_scope"] = result["scope"]
        if idempotency_key:
            self._idempotent_mutation_result[idempotency_key] = result
        return result

    async def set_kitty_runtime(
        self,
        hub_session_id: str,
        *,
        voice_session_id: Optional[str],
        agent_session_id: Optional[str],
        connected: bool,
    ) -> None:
        """Set kitty runtime."""
        async with self.session_lock:
            sess = self._sessions.get(hub_session_id)
            if sess is None:
                return
            sess.kitty_runtime.voice_session_id = voice_session_id
            sess.kitty_runtime.agent_session_id = agent_session_id
            sess.kitty_runtime.connected = bool(connected)

    async def get_mobile_kitty_diagram_bootstrap(
        self,
        user_id: int,
        *,
        client_suggested_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mobile Kitty: resolve diagram VoiceContext (live Redis desktop session, else library row).

        Single hub entry for ``GET /api/kitty/mobile_open_bootstrap`` and WS ``start`` fallback.
        """
        out = await resolve_mobile_open_bootstrap(
            int(user_id),
            client_suggested_scope=client_suggested_scope,
        )
        out["trace"] = {"request_id": _new_hub_request_id()}
        return out

    async def get_diagram_context(
        self,
        *,
        user_id: int,
        hub_session_id: Optional[str] = None,
        diagram_scope: Optional[str] = None,
        source_module: str,
        client_lane: Optional[str] = None,
        client_suggested_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get diagram context."""
        request_id = _new_hub_request_id()
        scope_hint = client_suggested_scope or diagram_scope
        bootstrap = await resolve_mobile_open_bootstrap(
            int(user_id),
            client_suggested_scope=scope_hint,
        )
        recommended_scope = bootstrap.get("recommended_scope")
        if hub_session_id and isinstance(recommended_scope, str) and recommended_scope.strip():
            await self.bind_scope(
                hub_session_id,
                diagram_scope=recommended_scope,
                source_module=source_module,
            )
        bootstrap["trace"] = {
            "request_id": request_id,
            "source_module": source_module,
            "client_lane": client_lane,
        }
        return bootstrap

    async def prepare_kitty_start_context(
        self,
        *,
        user_id: int,
        hub_session_id: Optional[str],
        diagram_scope: str,
        start_context: Dict[str, Any],
        start_diagram_type: str,
        start_active_panel: str,
        start_client_lane: Optional[str],
        source_module: str = "kitty",
    ) -> Dict[str, Any]:
        """Prepare kitty start context."""
        request_id = _new_hub_request_id()
        initial_context_in = copy.deepcopy(start_context) if isinstance(start_context, dict) else {}
        client_active_panel = initial_context_in.get("active_panel")
        client_one_sentence_phase = initial_context_in.get("one_sentence_phase")
        if start_client_lane == "mobile":
            lib_raw = initial_context_in.get("diagram_library_id")
            if not (isinstance(lib_raw, str) and lib_raw.strip()):
                boot = await self.get_diagram_context(
                    user_id=int(user_id),
                    hub_session_id=hub_session_id,
                    diagram_scope=diagram_scope,
                    source_module=source_module,
                    client_lane=start_client_lane,
                    client_suggested_scope=diagram_scope,
                )
                if boot.get("source") != "empty":
                    boot_context = boot.get("context")
                    if isinstance(boot_context, dict):
                        initial_context_in = copy.deepcopy(boot_context)
                    lang = start_context.get("interaction_language")
                    if isinstance(lang, str) and lang.strip():
                        initial_context_in["interaction_language"] = lang.strip()
                    start_diagram_type = str(boot.get("diagram_type") or start_diagram_type)
                    # Prefer client panel/phase when FE sent them so bootstrap "none"
                    # does not stomp mobile one_sentence routing.
                    if isinstance(client_active_panel, str) and client_active_panel.strip():
                        start_active_panel = client_active_panel.strip()
                        initial_context_in["active_panel"] = start_active_panel
                    else:
                        start_active_panel = str(boot.get("active_panel") or start_active_panel)
                    if isinstance(client_one_sentence_phase, str) and client_one_sentence_phase.strip():
                        initial_context_in["one_sentence_phase"] = client_one_sentence_phase.strip()

        prefer_mobile_server = start_client_lane == "mobile" and not diagram_data_has_visible_content(
            initial_context_in.get("diagram_data") or {}
        )
        merged_ctx, res_type, res_panel = await merge_voice_context_with_library(
            int(user_id),
            initial_context_in,
            diagram_type=start_diagram_type,
            active_panel=start_active_panel,
            prefer_server_diagram_nodes=prefer_mobile_server,
        )
        if start_client_lane == "mobile" and isinstance(client_active_panel, str) and client_active_panel.strip():
            res_panel = client_active_panel.strip()
            merged_ctx["active_panel"] = res_panel
        if (
            start_client_lane == "mobile"
            and isinstance(client_one_sentence_phase, str)
            and client_one_sentence_phase.strip()
        ):
            merged_ctx["one_sentence_phase"] = client_one_sentence_phase.strip()
        scope_norm = normalize_kitty_diagram_session_id(diagram_scope) or diagram_scope
        if hub_session_id:
            await self.bind_scope(
                hub_session_id,
                diagram_scope=scope_norm,
                source_module=source_module,
            )
        return {
            "context": merged_ctx,
            "diagram_type": res_type,
            "active_panel": res_panel,
            "trace": {"request_id": request_id},
        }

    async def apply_diagram_spec_mutation(
        self,
        *,
        hub_session_id: str,
        diagram_scope: str,
        mutation_cmd: Dict[str, Any],
        source_module: str,
        expected_revision: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply diagram spec mutation."""
        if idempotency_key and idempotency_key in self._idempotent_mutation_result:
            return self._idempotent_mutation_result[idempotency_key]

        scope_norm = normalize_kitty_diagram_session_id(diagram_scope)
        if scope_norm is None:
            raise ValueError("invalid diagram scope")
        async with self.session_lock:
            sess = self._sessions.get(hub_session_id)
            if sess is None:
                raise ValueError("hub session not found")
            if sess.binding is None or sess.binding.scope != scope_norm:
                sess.binding = HubScopeBinding(scope=scope_norm, revision=0)
            if expected_revision is not None and int(expected_revision) != int(sess.binding.revision):
                raise ValueError("stale expected revision")
            binding_revision = int(sess.binding.revision)
            user_id = int(sess.user_id)

        op_raw = mutation_cmd.get("op")
        op: MutationOp = "patch_context" if op_raw == "patch_context" else "replace_context"
        ctx_raw = mutation_cmd.get("context")
        if not isinstance(ctx_raw, dict):
            raise ValueError("mutation context is required")
        context_payload = copy.deepcopy(ctx_raw)
        diagram_type = str(mutation_cmd.get("diagram_type") or context_payload.get("diagram_type") or "circle_map")
        active_panel = str(mutation_cmd.get("active_panel") or context_payload.get("active_panel") or "none")

        if op == "patch_context":
            current_live = await resolve_mobile_open_bootstrap(user_id, client_suggested_scope=scope_norm)
            base_ctx = current_live.get("context")
            if not isinstance(base_ctx, dict):
                base_ctx = {}
            merged = {**base_ctx, **context_payload}
            raw_base_dd = base_ctx.get("diagram_data")
            base_dd: Dict[str, Any] = raw_base_dd if isinstance(raw_base_dd, dict) else {}
            raw_delta_dd = context_payload.get("diagram_data")
            delta_dd: Dict[str, Any] = raw_delta_dd if isinstance(raw_delta_dd, dict) else {}
            merged["diagram_data"] = {**base_dd, **delta_dd}
            context_payload = merged
            lib_id = context_payload.get("diagram_library_id")
            delta_has_visible = diagram_data_has_visible_content(delta_dd)
            if sess.client_lane == "mobile" and isinstance(lib_id, str) and lib_id.strip():
                merged_ctx, res_dt, res_panel = await merge_voice_context_with_library(
                    user_id,
                    context_payload,
                    diagram_type=diagram_type,
                    active_panel=active_panel,
                    prefer_server_diagram_nodes=not delta_has_visible,
                )
                context_payload = merged_ctx
                diagram_type = res_dt
                active_panel = res_panel

        mut_id = _new_hub_mutation_id()
        request_id = _new_hub_request_id()
        persist_order = ["library_snapshot", "live_spec"]
        library_saved = False
        lib_error: Optional[str] = None
        lib_snapshot = mutation_cmd.get("library_snapshot")
        if isinstance(lib_snapshot, dict) and bool(mutation_cmd.get("persist_library")):
            lib_id = context_payload.get("diagram_library_id")
            if isinstance(lib_id, str) and lib_id.strip():
                spec = lib_snapshot.get("spec")
                if isinstance(spec, dict):
                    title_raw = lib_snapshot.get("title") or context_payload.get("diagram_display_title") or "Untitled"
                    title = str(title_raw).strip() or "Untitled"
                    language = str(lib_snapshot.get("language") or "zh")
                    thumbnail = lib_snapshot.get("thumbnail")
                    ok, _saved_id, err = await get_diagram_cache().save_diagram(
                        user_id=user_id,
                        diagram_id=lib_id,
                        title=title,
                        diagram_type=diagram_type,
                        spec=spec,
                        language=language,
                        thumbnail=thumbnail if isinstance(thumbnail, str) else None,
                    )
                    library_saved = bool(ok)
                    lib_error = err if isinstance(err, str) else None

        updated_at = await upsert_kitty_redis_session(
            scope_norm,
            user_id,
            active_diagram_library_id=(
                context_payload.get("diagram_library_id")
                if isinstance(context_payload.get("diagram_library_id"), str)
                else None
            ),
            live_payload={
                "diagram_type": diagram_type,
                "active_panel": active_panel,
                "diagram_data": context_payload.get("diagram_data") or {},
                "selected_nodes": context_payload.get("selected_nodes") or [],
                "diagram_library_id": context_payload.get("diagram_library_id"),
                "diagram_display_title": context_payload.get("diagram_display_title"),
            },
            client_lane=sess.client_lane if sess.client_lane == "mobile" else None,
        )

        async with self.session_lock:
            sess_after = self._sessions.get(hub_session_id)
            if sess_after and sess_after.binding and sess_after.binding.scope == scope_norm:
                sess_after.binding.revision = binding_revision + 1
                sess_after.binding.last_mutation_id = mut_id
                new_revision = sess_after.binding.revision
            else:
                new_revision = binding_revision + 1

        result = {
            "ok": True,
            "scope": scope_norm,
            "revision": new_revision,
            "persist_order": persist_order,
            "library_snapshot_saved": library_saved,
            "library_snapshot_error": lib_error,
            "live_spec_updated_at": updated_at,
            "trace": {
                "request_id": request_id,
                "mutation_id": mut_id,
                "idempotency_key": idempotency_key,
                "source_module": source_module,
            },
        }
        logger.info(
            "[AgentHub] mutation applied scope=%s session=%s op=%s source=%s request_id=%s mutation_id=%s",
            scope_norm,
            hub_session_id,
            op,
            source_module,
            request_id,
            mut_id,
            extra=kitty_extra("hub_mutation_applied", scope=scope_norm, user_id=user_id),
        )
        if idempotency_key:
            self._idempotent_mutation_result[idempotency_key] = result
        return result

    async def preempt_scope(self, scope: str, user_id: int, reason: str) -> None:
        """Publish cross-worker close-scope (handshake preempt, idle, HTTP)."""
        await publish_kitty_close_scope_async(scope, int(user_id), reason)

    async def preempt_handshake(self, scope: str, user_id: int) -> None:
        """Preempt handshake."""
        await self.preempt_scope(scope, user_id, KITTY_CONTROL_REASON_HANDSHAKE_PREEMPT)

    async def preempt_idle_timeout(self, scope: str, user_id: int) -> None:
        """Preempt idle timeout."""
        await self.preempt_scope(scope, user_id, KITTY_CONTROL_REASON_IDLE_TIMEOUT)

    async def register_kitty_connection(self, scope: str, user_id: int) -> bool:
        """Call after successful WS ``start`` + Redis upsert (global refcount)."""
        count = await kitty_scope_refcount_attach(scope)
        if count is None:
            record_kitty_refcount_attach_failed()
            logger.warning(
                "[AgentHub] refcount attach failed scope=%s user_id=%s (no Redis or script error)",
                scope,
                user_id,
                extra=kitty_extra("refcount_attach_failed", scope=scope, user_id=user_id),
            )
            return False
        record_kitty_refcount_attach()
        logger.debug(
            "[AgentHub] refcount attach scope=%s user_id=%s count=%s",
            scope,
            user_id,
            count,
        )
        return True

    async def unregister_kitty_connection(self, scope: str, user_id: int) -> None:
        """Call from WS ``finally`` after removing socket from ``active_websockets``."""
        result = await kitty_scope_refcount_detach(scope, user_id)
        if result is None:
            record_kitty_refcount_detach_failed()
            logger.warning(
                "[AgentHub] refcount detach failed scope=%s user_id=%s (no Redis or script error)",
                scope,
                user_id,
                extra=kitty_extra("refcount_detach_failed", scope=scope, user_id=user_id),
            )
            return
        if result == KittyDetachResult.OWNER_MISMATCH_ROLLBACK:
            record_kitty_refcount_detach_mismatch()
            logger.warning(
                "[AgentHub] refcount detach owner mismatch scope=%s user_id=%s",
                scope,
                user_id,
                extra=kitty_extra("refcount_detach_owner_mismatch", scope=scope, user_id=user_id),
            )
        elif result == KittyDetachResult.KEYS_REMOVED:
            record_kitty_refcount_teardown()
            logger.debug("[AgentHub] refcount teardown scope=%s user_id=%s", scope, user_id)
        elif result is not None and result > 0:
            logger.debug(
                "[AgentHub] refcount detach scope=%s user_id=%s remaining=%s",
                scope,
                user_id,
                result,
            )

    def validate_tier_b_pairing_token(self, _scope: str, _user_id: int, _token: Optional[str]) -> bool:
        """
        Reserved for Tier-B signed pairing tokens (QR / short code).

        Not implemented: always valid when token omitted.
        """
        return _token is None or str(_token).strip() == ""
