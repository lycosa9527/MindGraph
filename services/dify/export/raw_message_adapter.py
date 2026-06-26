"""
Convert raw Dify CSV rows to Service-API-shaped message dicts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional


def _parse_epoch(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp())
    except ValueError:
        return 0


def row_to_api_message(
    row: dict,
    *,
    files: Optional[List[dict]] = None,
    feedback_rating: Optional[str] = None,
) -> dict:
    """Map one messages.csv row (+ enrichments) to Dify API message shape."""
    message_id = str(row.get("id") or "")
    payload: Dict[str, Any] = {
        "id": message_id,
        "conversation_id": str(row.get("conversation_id") or ""),
        "query": row.get("query") or "",
        "answer": row.get("answer") or "",
        "created_at": _parse_epoch(row.get("created_at")),
        "message_files": list(files or []),
    }
    status = str(row.get("status") or "").strip().lower()
    if status:
        payload["status"] = status
    if feedback_rating:
        payload["feedback"] = {"rating": feedback_rating}
    return payload


def api_message_files_from_rows(file_rows: List[dict]) -> List[dict]:
    """Convert message_files.csv rows to API message_files list."""
    out: List[dict] = []
    for row in file_rows:
        out.append(
            {
                "id": str(row.get("id") or ""),
                "type": row.get("type") or "",
                "url": row.get("url") or "",
                "belongs_to": row.get("belongs_to") or "",
                "transfer_method": row.get("transfer_method") or "",
            }
        )
    return out


def conversation_updated_at(row: dict) -> int:
    """Epoch seconds from conversations.csv updated_at (fallback created_at)."""
    updated = _parse_epoch(row.get("updated_at"))
    if updated:
        return updated
    return _parse_epoch(row.get("created_at"))


def conversation_created_at(row: dict) -> int:
    """Epoch seconds from conversations.csv created_at."""
    return _parse_epoch(row.get("created_at"))
