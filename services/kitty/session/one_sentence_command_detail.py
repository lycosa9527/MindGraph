"""Build and sanitize one-sentence command_detail payloads for activity tracking.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

# Keep JSONB rows bounded for analytics queries.
_MAX_DETAIL_CHARS = 8000
_COMMAND_KEYS = (
    "action",
    "target",
    "node_id",
    "node_index",
    "new_text",
    "text",
    "confidence",
    "parent_id",
    "side",
)


def _clip_str(value: Any, *, max_len: int = 500) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _sanitize_command(command: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(command, Mapping):
        return {}
    out: Dict[str, Any] = {}
    for key in _COMMAND_KEYS:
        if key not in command:
            continue
        raw = command.get(key)
        if isinstance(raw, (int, float, bool)):
            out[key] = raw
        else:
            clipped = _clip_str(raw)
            if clipped is not None:
                out[key] = clipped
    follow_ups = command.get("follow_up_actions")
    if isinstance(follow_ups, list) and follow_ups:
        names: list[str] = []
        for item in follow_ups[:5]:
            if isinstance(item, dict):
                name = _clip_str(item.get("action"), max_len=64)
                if name:
                    names.append(name)
        if names:
            out["follow_up_actions"] = names
    return out


def _sanitize_bus(tool_result: Any | None) -> Dict[str, Any]:
    if tool_result is None:
        return {}
    to_dict = getattr(tool_result, "to_dict", None)
    if callable(to_dict):
        raw = to_dict()
    elif isinstance(tool_result, Mapping):
        raw = dict(tool_result)
    else:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    status = _clip_str(raw.get("status"), max_len=32)
    if status:
        out["status"] = status
    mutation_id = _clip_str(raw.get("mutation_id"), max_len=64)
    if mutation_id:
        out["mutation_id"] = mutation_id
    if raw.get("revision") is not None:
        try:
            out["revision"] = int(raw["revision"])
        except (TypeError, ValueError):
            pass
    error_code = _clip_str(raw.get("error_code"), max_len=64)
    if error_code:
        out["error_code"] = error_code
    message = _clip_str(raw.get("message"), max_len=240)
    if message:
        out["message"] = message
    applied = raw.get("applied_ops")
    if isinstance(applied, list) and applied:
        ops: list[Dict[str, Any]] = []
        for item in applied[:12]:
            if not isinstance(item, dict):
                continue
            op_row: Dict[str, Any] = {}
            for key in ("op", "text", "node_id", "parent_id", "side"):
                clipped = _clip_str(item.get(key), max_len=200)
                if clipped is not None:
                    op_row[key] = clipped
            if op_row:
                ops.append(op_row)
        if ops:
            out["applied_ops"] = ops
    return out


def build_one_sentence_command_detail(
    *,
    action: str | None = None,
    outcome: str | None = None,
    command: Mapping[str, Any] | None = None,
    tool_result: Any | None = None,
    error_code: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build a compact activity payload for diagram node actions.

    Stored on kitty turns as ``command_detail`` so analytics can answer
    what action ran, on which node, and whether Bus applied it.
    """
    detail: Dict[str, Any] = {}
    action_name = _clip_str(action, max_len=64)
    if action_name:
        detail["action"] = action_name
    outcome_name = _clip_str(outcome, max_len=32)
    if outcome_name:
        detail["outcome"] = outcome_name

    command_part = _sanitize_command(command)
    if command_part:
        detail["command"] = command_part

    bus_part = _sanitize_bus(tool_result)
    if error_code and "error_code" not in bus_part:
        clipped_err = _clip_str(error_code, max_len=64)
        if clipped_err:
            bus_part["error_code"] = clipped_err
    if bus_part:
        detail["bus"] = bus_part

    if isinstance(extra, Mapping):
        for key, value in extra.items():
            if key in detail or value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                detail[str(key)[:64]] = (
                    value if not isinstance(value, str) else (value if len(value) <= 200 else value[:199] + "…")
                )

    encoded = json.dumps(detail, ensure_ascii=False, default=str)
    if len(encoded) <= _MAX_DETAIL_CHARS:
        return detail
    # Drop applied_ops first, then command extras.
    if "bus" in detail and isinstance(detail["bus"], dict):
        detail["bus"].pop("applied_ops", None)
    if "command" in detail and isinstance(detail["command"], dict):
        detail["command"].pop("follow_up_actions", None)
    return detail


def normalize_command_detail(raw: Any) -> Optional[Dict[str, Any]]:
    """Accept dict or JSON string; return a bounded dict or None."""
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        raw = parsed
    if not isinstance(raw, dict) or not raw:
        return None
    encoded = json.dumps(raw, ensure_ascii=False, default=str)
    if len(encoded) > _MAX_DETAIL_CHARS:
        return None
    return dict(raw)
