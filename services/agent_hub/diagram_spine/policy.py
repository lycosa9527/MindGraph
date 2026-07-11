"""Injectable diagram command policy — Kitty implementation first."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from services.diagram_edit.pending import new_mutation_id
from services.diagram_edit.types import ErrorCode, ToolResult
from services.kitty.infra.scope.kitty_scope_access import user_may_access_kitty_scope


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


def _write_lock_busy(session_context: Dict[str, Any]) -> bool:
    lock_raw = session_context.get("diagram_write_lock")
    if not isinstance(lock_raw, dict):
        return False
    holder = lock_raw.get("holder")
    return holder == "llm"


class DiagramCommandPolicy(Protocol):
    """Policy checks before diagram edit dispatch."""

    async def validate(
        self,
        *,
        scope: str,
        session_context: Dict[str, Any],
        live_session: Optional[Dict[str, Any]],
        user_id: Optional[int],
        expected_revision: Optional[int],
    ) -> Optional[ToolResult]:
        """Return rejection ToolResult or None when checks pass."""


class KittyDiagramCommandPolicy:
    """Kitty voice scope access, owner, revision, and write-lock checks."""

    async def validate(
        self,
        *,
        scope: str,
        session_context: Dict[str, Any],
        live_session: Optional[Dict[str, Any]],
        user_id: Optional[int],
        expected_revision: Optional[int],
    ) -> Optional[ToolResult]:
        """Return rejection ToolResult or None when checks pass."""
        mutation_id = new_mutation_id()

        if not scope.strip():
            return _rejected(mutation_id, "no_owner", "Missing diagram scope")

        if live_session is None:
            return _rejected(mutation_id, "no_owner", "No bound voice session")

        if user_id is not None:
            allowed = await user_may_access_kitty_scope(user_id, scope)
            if not allowed:
                return _rejected(mutation_id, "access_denied")

        if _write_lock_busy(session_context):
            return _rejected(mutation_id, "busy_llm_generating")

        hub_rev_raw = live_session.get("_hub_scope_revision")
        hub_rev = hub_rev_raw if isinstance(hub_rev_raw, int) else None
        if expected_revision is not None and hub_rev is not None:
            if int(expected_revision) != int(hub_rev):
                return _rejected(mutation_id, "stale_revision")

        return None


def get_default_diagram_policy() -> KittyDiagramCommandPolicy:
    """Process-wide default Kitty policy."""
    return KittyDiagramCommandPolicy()
