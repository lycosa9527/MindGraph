"""Dedup fingerprint helpers for PG-to-PG merge."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, Optional, Tuple

DedupFingerprintFn = Callable[[Dict[str, Any]], Optional[Tuple[Any, ...]]]


def normalize_dedup_value(value: Any) -> Any:
    """Normalize values used in dedup keys (e.g. datetime string vs object)."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.replace(tzinfo=None)
    return value


def dedup_tuple(values: Dict[str, Any], columns: Tuple[str, ...]) -> Tuple[Any, ...]:
    """Build a normalized dedup key tuple from row values."""
    return tuple(normalize_dedup_value(values.get(col)) for col in columns)


def mindbot_usage_event_fingerprint(values: Dict[str, Any]) -> Optional[Tuple[Any, ...]]:
    """Stable key for mindbot_usage_events rows."""
    msg_id = values.get("msg_id")
    if msg_id:
        return (values.get("organization_id"), msg_id)
    return (
        values.get("organization_id"),
        values.get("dingtalk_staff_id"),
        values.get("created_at"),
        values.get("dify_user_key"),
    )


def chat_channel_fingerprint(values: Dict[str, Any]) -> Optional[Tuple[Any, ...]]:
    """Live announce is a singleton; other channels unique on org/parent/name."""
    archived = bool(values.get("is_archived"))
    if values.get("channel_type") == "announce" and not archived:
        return ("announce",)
    created_at = normalize_dedup_value(values.get("created_at")) if archived else None
    return (
        values.get("organization_id"),
        values.get("parent_id"),
        values.get("name"),
        archived,
        created_at,
    )


DEDUP_FINGERPRINT_FNS: Dict[str, DedupFingerprintFn] = {
    "mindbot_usage_event": mindbot_usage_event_fingerprint,
    "chat_channel": chat_channel_fingerprint,
}


def fingerprint_key(fn_name: str, values: Dict[str, Any]) -> Optional[Tuple[Any, ...]]:
    """Return composite dedup tuple for tables using ``dedup_fingerprint`` config."""
    fn = DEDUP_FINGERPRINT_FNS.get(fn_name)
    if fn is None:
        return None
    return fn(values)
