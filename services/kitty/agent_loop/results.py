"""Tool-result payloads for the typed Kitty agent loop.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.diagram_edit.types import ToolResult

PENDING_AUTOCOMPLETE_KEY = "_pending_autocomplete_observe"
ONE_SENTENCE_REQUEST_ID_KEY = "_one_sentence_request_id"
STACKED_PROGRESS_KEY = "_stacked_progress_pending"

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


def autocomplete_started_content(
    *,
    action: str,
    node_id: Optional[str] = None,
    target: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Honest generate-start observation — never ``applied``."""
    extra: Dict[str, Any] = {"started": True}
    if node_id:
        extra["node_id"] = node_id
    if target:
        extra["target"] = target
    if job_id:
        extra["job_id"] = job_id
    return ui_result_content(status="started", action=action, extra=extra)


def arm_pending_autocomplete(
    session: Optional[Dict[str, Any]],
    *,
    action: str,
    node_id: Optional[str] = None,
    target: Optional[str] = None,
) -> None:
    """Remember an in-flight canvas generate so a later finish can be observed."""
    if not isinstance(session, dict):
        return
    pending: Dict[str, Any] = {"action": action, "started": True}
    if node_id:
        pending["node_id"] = node_id
    if target:
        pending["target"] = target
    request_id = session_one_sentence_request_id(session)
    if request_id:
        pending["request_id"] = request_id
    session.pop(STACKED_PROGRESS_KEY, None)
    session[PENDING_AUTOCOMPLETE_KEY] = pending


def finish_pending_autocomplete(
    session: Optional[Dict[str, Any]],
    *,
    status: str = "finished",
    node_id: Optional[str] = None,
    message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Consume the pending generate and return a finish/fail observation."""
    if not isinstance(session, dict):
        return None
    raw = session.pop(PENDING_AUTOCOMPLETE_KEY, None)
    if not isinstance(raw, dict):
        return None
    action = str(raw.get("action") or "auto_complete")
    extra: Dict[str, Any] = {}
    resolved_id = node_id or raw.get("node_id")
    if isinstance(resolved_id, str) and resolved_id.strip():
        extra["node_id"] = resolved_id.strip()
    target = raw.get("target")
    if isinstance(target, str) and target.strip():
        extra["target"] = target.strip()
    request_id = _trim_request_id(raw.get("request_id"))
    if request_id:
        extra["request_id"] = request_id
    normalized = status.strip().lower() if status.strip() else "finished"
    if normalized not in {"finished", "failed"}:
        normalized = "finished"
    return ui_result_content(
        status=normalized,
        action=action,
        message=message,
        extra=extra or None,
    )


def session_one_sentence_request_id(session: Optional[Dict[str, Any]]) -> Optional[str]:
    """Current one-sentence request id on the voice session, if any."""
    if not isinstance(session, dict):
        return None
    return _trim_request_id(session.get(ONE_SENTENCE_REQUEST_ID_KEY))


def autocomplete_observation_is_stale(
    session: Optional[Dict[str, Any]],
    observation: Dict[str, Any],
) -> bool:
    """True when a pending generate belongs to an earlier one-sentence turn."""
    pending_id = _trim_request_id(observation.get("request_id"))
    if pending_id is None:
        return False
    return session_one_sentence_request_id(session) != pending_id


def _trim_request_id(raw: Any) -> Optional[str]:
    """Return a non-empty request id, or None."""
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def mark_stacked_progress_pending(
    session: Optional[Dict[str, Any]],
    *,
    action: str,
    text: str,
) -> None:
    """Remember a mid-stack thinking line so the loop can promote it if fill never starts."""
    if not isinstance(session, dict):
        return
    trimmed = text.strip()
    if not trimmed:
        return
    session[STACKED_PROGRESS_KEY] = {"action": action, "text": trimmed}


def take_stacked_progress_pending(session: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Consume a deferred stacked-job thinking line."""
    if not isinstance(session, dict):
        return None
    raw = session.pop(STACKED_PROGRESS_KEY, None)
    if not isinstance(raw, dict):
        return None
    action = str(raw.get("action") or "").strip()
    text = str(raw.get("text") or "").strip()
    if not text:
        return None
    return {"action": action or "multi_step", "text": text}


def should_keep_pending_autocomplete(session_context: Dict[str, Any]) -> bool:
    """True while the canvas still holds the LLM generate lock."""
    lock = session_context.get("diagram_write_lock")
    if not isinstance(lock, dict):
        return False
    holder = lock.get("holder")
    return holder == "llm"


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
