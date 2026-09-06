"""Operator-facing audit lines for 校本培训 (course builder + live follow).

Messages stay greppable in plain logs: ``[Training] course_created course_id=...``.
Structured ``tr_*`` keys ride on ``extra`` for JSON backends.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

_SCOPE_KEYS = ("actor_id", "org_id", "course_id", "session_id")


def bilingual_label(value: Any) -> str:
    """Prefer zh, then en, from a bilingual JSON field."""
    if isinstance(value, dict):
        text = value.get("zh") or value.get("en") or ""
        return str(text).strip()
    if value is None:
        return ""
    return str(value).strip()


def step_type_summary(steps: list[dict[str, Any]] | None) -> str:
    """Compact step inventory, or ``unchanged`` when the save omitted steps."""
    if steps is None:
        return "unchanged"
    counts: dict[str, int] = {}
    for raw in steps:
        kind = str(raw.get("type") or raw.get("step_type") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    if not counts:
        return "0"
    parts = [f"{name}:{counts[name]}" for name in sorted(counts)]
    return f"{len(steps)}({','.join(parts)})"


def _format_field(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def format_training_line(event: str, *, prefix: str = "[Training]", **fields: Any) -> str:
    """Build ``[Training] event key=value`` with empty fields omitted."""
    parts = [f"{prefix} {event}"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={_format_field(value)}")
    return " ".join(parts)


def training_extra(
    *,
    event: str,
    actor_id: int | str = "",
    org_id: int | str = "",
    course_id: str = "",
    session_id: str = "",
    **more: Any,
) -> dict[str, Any]:
    """Build a single ``extra`` dict with stable ``tr_*`` keys."""
    payload: dict[str, Any] = {
        "tr_event": event,
        "tr_actor_id": actor_id if actor_id != "" else "",
        "tr_org_id": org_id if org_id != "" else "",
        "tr_course_id": course_id if course_id != "" else "",
        "tr_session_id": session_id if session_id != "" else "",
    }
    for key, value in more.items():
        prefixed = key if key.startswith("tr_") else f"tr_{key}"
        payload[prefixed] = value
    return payload


def log_training(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit one training audit line (default INFO)."""
    level = int(fields.pop("level", logging.INFO))
    prefix = str(fields.pop("prefix", "[Training]"))
    scope = {key: fields.pop(key, "") for key in _SCOPE_KEYS}
    message = format_training_line(event, prefix=prefix, **scope, **fields)
    logger.log(level, message, extra=training_extra(event=event, **scope, **fields))
