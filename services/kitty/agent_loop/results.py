"""Tool-result payloads for the typed Kitty agent loop.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.diagram_edit.types import ToolResult

NONRETRYABLE_ERROR_CODES = frozenset(
    {
        "access_denied",
        "no_owner",
        "collab_active",
        "busy_llm_generating",
    }
)

RETRYABLE_ERROR_CODES = frozenset(
    {
        "verify_failed",
        "stale_revision",
        "apply_noop",
        "ack_timeout",
        "not_parsed",
    }
)


def tool_result_content(result: ToolResult) -> Dict[str, Any]:
    """JSON object stored in a ``role: tool`` message for a structural apply."""
    return result.to_dict()


def ui_result_content(
    *,
    status: str,
    action: str,
    message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """JSON object for non-structural tools (do not fake ``applied`` verify)."""
    payload: Dict[str, Any] = {"status": status, "action": action}
    if message:
        payload["message"] = message
    if extra:
        payload.update(extra)
    return payload


def encode_tool_content(payload: Dict[str, Any]) -> str:
    """Serialize tool content for the OpenAI-compatible ``role: tool`` row."""
    return json.dumps(payload, ensure_ascii=False)


def created_node_ids_from_payload(payload: Dict[str, Any]) -> List[str]:
    """Collect canvas ids assigned by a structural apply."""
    ids: List[str] = []
    applied_ops = payload.get("applied_ops")
    if isinstance(applied_ops, list):
        for item in applied_ops:
            if not isinstance(item, dict):
                continue
            node_id = item.get("node_id")
            if isinstance(node_id, str) and node_id.strip():
                ids.append(node_id.strip())
    raw_created = payload.get("created_node_ids")
    if isinstance(raw_created, list):
        for item in raw_created:
            if isinstance(item, str) and item.strip() and item.strip() not in ids:
                ids.append(item.strip())
    return ids


def is_nonretryable_error(error_code: Optional[str]) -> bool:
    """True when the loop must stop (policy / owner / lock)."""
    return error_code in NONRETRYABLE_ERROR_CODES


def is_retryable_error(error_code: Optional[str]) -> bool:
    """True when the model may try another tool call."""
    return error_code in RETRYABLE_ERROR_CODES


def summarize_payload_for_memory(payload: Dict[str, Any], *, action: str) -> str:
    """One-line observation for session memory (not a second message dialect)."""
    status = str(payload.get("status") or "")
    revision = payload.get("revision")
    error_code = payload.get("error_code")
    created = created_node_ids_from_payload(payload)
    parts = [action, status]
    if revision is not None:
        parts.append(f"rev={revision}")
    if error_code:
        parts.append(str(error_code))
    if created:
        parts.append(f"created={','.join(created[:3])}")
    return " ".join(parts)


def error_code_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Return error_code from a tool payload when present."""
    raw = payload.get("error_code")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
