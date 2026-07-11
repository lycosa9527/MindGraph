"""Diagram Edit Tool — shared types and envelopes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, get_args

DiagramEditStatus = Literal["applied", "failed", "rejected"]

ErrorCode = Literal[
    "not_parsed",
    "unsupported_tool",
    "unsupported_diagram_type",
    "no_owner",
    "stale_revision",
    "apply_noop",
    "verify_failed",
    "ack_timeout",
    "compensate_failed",
    "access_denied",
    "busy_llm_generating",
    "hub_persist_failed",
]


def coerce_error_code(raw: Optional[str], default: ErrorCode) -> ErrorCode:
    """Map an arbitrary string to a known ErrorCode, else ``default``."""
    for code in get_args(ErrorCode):
        if raw == code:
            return code
    return default


MINDMAP_DIAGRAM_TYPES = frozenset({"mindmap", "mind_map"})

STRUCTURAL_TOOLS = frozenset(
    {
        "diagram.update_center",
        "diagram.add_node",
        "diagram.update_node",
        "diagram.delete_node",
    }
)

LEGACY_ACTION_TO_TOOL = {
    "update_center": "diagram.update_center",
    "add_node": "diagram.add_node",
    "update_node": "diagram.update_node",
    "delete_node": "diagram.delete_node",
}


@dataclass(slots=True)
class DiagramEditCommand:
    """Agent mutation request envelope."""

    tool: str
    args: Dict[str, Any]
    scope: str
    diagram_type: str
    expected_revision: Optional[int] = None
    idempotency_key: Optional[str] = None
    source_agent: str = "kitty"
    legacy_action: Optional[str] = None
    legacy_command: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class ExpectedEffect:
    """Postcondition checklist the owning canvas must prove."""

    op: str
    text: Optional[str] = None
    parent_ref: Optional[str] = None
    side: Optional[str] = None
    node_id: Optional[str] = None
    node_identifier: Optional[str] = None
    checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize expected effect for WS outbound."""
        payload: Dict[str, Any] = {"op": self.op, "checks": list(self.checks)}
        if self.text is not None:
            payload["text"] = self.text
        if self.parent_ref is not None:
            payload["parent_ref"] = self.parent_ref
        if self.side is not None:
            payload["side"] = self.side
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.node_identifier is not None:
            payload["node_identifier"] = self.node_identifier
        return payload


@dataclass(slots=True)
class VerificationReport:
    """Verification outcome from owning canvas or server re-check."""

    ok: bool
    checks: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize verification report."""
        out: Dict[str, Any] = {"ok": self.ok, "checks": list(self.checks)}
        if self.error:
            out["error"] = self.error
        return out


@dataclass(slots=True)
class ToolResult:
    """Machine-readable mutation result; applied means verified on canvas."""

    status: DiagramEditStatus
    mutation_id: str
    revision: Optional[int] = None
    applied_ops: List[Dict[str, Any]] = field(default_factory=list)
    verification: Optional[VerificationReport] = None
    error_code: Optional[ErrorCode] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tool result envelope."""
        out: Dict[str, Any] = {
            "status": self.status,
            "mutation_id": self.mutation_id,
            "applied_ops": list(self.applied_ops),
        }
        if self.revision is not None:
            out["revision"] = self.revision
        if self.verification is not None:
            out["verification"] = self.verification.to_dict()
        if self.error_code is not None:
            out["error_code"] = self.error_code
        if self.message is not None:
            out["message"] = self.message
        return out
