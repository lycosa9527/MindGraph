"""Extract token usage from Dify chat-messages responses (blocking JSON or SSE events)."""

from __future__ import annotations

from typing import Any, Optional


def _coerce_usage_dict(usage: dict[str, Any]) -> Optional[dict[str, int]]:
    if not isinstance(usage, dict):
        return None

    def _int_val(key: str) -> int:
        raw = usage.get(key)
        if isinstance(raw, bool):
            return 0
        if isinstance(raw, int):
            return max(0, raw)
        if isinstance(raw, float):
            return max(0, int(raw))
        return 0

    pt = _int_val("prompt_tokens")
    ct = _int_val("completion_tokens")
    tt = _int_val("total_tokens")
    if not tt and (pt or ct):
        tt = pt + ct
    if pt == 0 and ct == 0 and tt == 0:
        return None
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}


def parse_dify_usage_from_stream_event(ev: dict[str, Any]) -> Optional[dict[str, int]]:
    """``message_end`` (and similar) may include ``metadata.usage``."""
    meta = ev.get("metadata")
    if not isinstance(meta, dict):
        return None
    u = meta.get("usage")
    if not isinstance(u, dict):
        return None
    return _coerce_usage_dict(u)


def parse_dify_usage_from_blocking_response(resp: dict[str, Any]) -> Optional[dict[str, int]]:
    """Blocking ``/chat-messages`` JSON often exposes ``metadata.usage``."""
    meta = resp.get("metadata")
    if not isinstance(meta, dict):
        return None
    u = meta.get("usage")
    if not isinstance(u, dict):
        return None
    return _coerce_usage_dict(u)
