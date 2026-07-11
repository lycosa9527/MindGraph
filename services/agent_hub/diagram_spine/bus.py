"""DiagramCommandBus — single front door for agent diagram mutations."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import WebSocket

from services.agent_hub.diagram_spine.policy import (
    DiagramCommandPolicy,
    get_default_diagram_policy,
)
from services.agent_hub.diagram_spine.types import DiagramCommandRequest, DiagramCommandResult
from services.diagram_edit.convert import legacy_command_to_diagram_edit
from services.diagram_edit.executor import execute_diagram_edit
from services.diagram_edit.pending import new_mutation_id
from services.diagram_edit.transport.kitty_ws import KittyWsTransport
from services.diagram_edit.transport.protocol import CanvasTransport
from services.diagram_edit.types import ErrorCode, ToolResult
from services.kitty.diagram.diagram_execute import execute_diagram_update

logger = logging.getLogger(__name__)


def _failed(mutation_id: str, error_code: ErrorCode, message: Optional[str] = None) -> ToolResult:
    return ToolResult(
        status="failed",
        mutation_id=mutation_id,
        error_code=error_code,
        message=message,
    )


class DiagramCommandBus:
    """Front door: policy → diagram edit tool → combined ack (when verify_required)."""

    def __init__(
        self,
        *,
        policy: Optional[DiagramCommandPolicy] = None,
        transport: Optional[CanvasTransport] = None,
    ) -> None:
        self._policy = policy or get_default_diagram_policy()
        self._transport: CanvasTransport = transport or KittyWsTransport()

    async def apply(
        self,
        websocket: WebSocket,
        request: DiagramCommandRequest,
    ) -> DiagramCommandResult:
        """Validate policy and execute diagram edit for the request."""
        live = self._transport.get_live_session(request.voice_session_id)
        hub_rev = self._transport.get_hub_revision(request.voice_session_id)
        expected_revision = hub_rev if request.verify_required else None

        rejection = await self._policy.validate(
            scope=request.scope,
            session_context=request.session_context,
            live_session=live,
            user_id=request.user_id,
            expected_revision=expected_revision,
        )
        if rejection is not None:
            return DiagramCommandResult(
                tool_result=rejection,
                hub_revision=hub_rev,
                origin=request.origin,
            )

        cmd = legacy_command_to_diagram_edit(
            request.legacy_command,
            scope=request.scope,
            diagram_type=request.diagram_type,
            expected_revision=expected_revision,
            idempotency_key=request.idempotency_key,
            source_agent=request.source_agent,
        )
        if cmd is None:
            fail = _failed(new_mutation_id(), "not_parsed", "Could not map legacy command")
            return DiagramCommandResult(
                tool_result=fail,
                hub_revision=hub_rev,
                origin=request.origin,
            )

        if not request.verify_required:
            tool_result = await self._apply_legacy_voice(websocket, request, cmd.legacy_action)
            result_rev = tool_result.revision if tool_result.status == "applied" else hub_rev
            return DiagramCommandResult(
                tool_result=tool_result,
                hub_revision=result_rev,
                origin=request.origin,
            )

        tool_result = await execute_diagram_edit(
            websocket,
            request.voice_session_id,
            cmd,
            request.session_context,
            user_id=request.user_id,
            transport=self._transport,
            verify_required=request.verify_required,
            require_hub_persist=request.verify_required,
        )

        result_rev = tool_result.revision if tool_result.status == "applied" else hub_rev
        logger.debug(
            "[DiagramCommandBus] apply origin=%s status=%s mutation=%s",
            request.origin.value,
            tool_result.status,
            tool_result.mutation_id,
        )
        return DiagramCommandResult(
            tool_result=tool_result,
            hub_revision=result_rev,
            origin=request.origin,
        )

    async def _apply_legacy_voice(
        self,
        websocket: WebSocket,
        request: DiagramCommandRequest,
        action: Optional[str],
    ) -> ToolResult:
        """Legacy Kitty voice path (all diagram types, no verified ack)."""
        mutation_id = new_mutation_id()
        if not isinstance(action, str) or not action.strip():
            return _failed(mutation_id, "not_parsed", "Missing legacy action")

        executed = await execute_diagram_update(
            websocket,
            request.voice_session_id,
            action.strip(),
            request.legacy_command,
            request.session_context,
        )
        if not executed:
            return _failed(mutation_id, "apply_noop", "Legacy diagram_execute returned false")

        hub_rev = self._transport.get_hub_revision(request.voice_session_id)
        return ToolResult(
            status="applied",
            mutation_id=mutation_id,
            revision=hub_rev,
        )


class _DiagramCommandBusState:
    """Process-wide diagram command bus singleton holder."""

    instance: Optional[DiagramCommandBus] = None


def get_diagram_command_bus() -> DiagramCommandBus:
    """Get diagram command bus."""
    if _DiagramCommandBusState.instance is None:
        _DiagramCommandBusState.instance = DiagramCommandBus()
    return _DiagramCommandBusState.instance
