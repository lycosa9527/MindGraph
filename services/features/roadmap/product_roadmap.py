"""
Load the product roadmap from one shared COS object.

The key is ``shared/roadmap/product_roadmap.json``. It is not passed through
``cos_feature_prefix``, so dev, test, and production read the same file.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Optional, TypedDict
from zoneinfo import ZoneInfo

from services.utils.tencent_cos_client import get_object_bytes, upload_bytes

ROADMAP_OBJECT_KEY = "shared/roadmap/product_roadmap.json"
ROADMAP_COLUMNS = ("now", "next", "later", "shipped")
_COLUMN_SET = frozenset(ROADMAP_COLUMNS)
_TARGET_RE = re.compile(r"^20\d{2}年(?:[1-9]|1[0-2])月$")
_MAX_BYTES = 256 * 1024
_MAX_ITEMS = 80
_MAX_TEXT = 400
_CACHE_SECONDS = 30.0


class RoadmapItemDict(TypedDict):
    """One card on the roadmap."""

    column: str
    title: str
    summary: str
    owner: str
    area: str
    target: str


class RoadmapDict(TypedDict):
    """Roadmap payload returned to the modal."""

    updated_at: str
    items: list[RoadmapItemDict]


class RoadmapWriteError(Exception):
    """The shared COS object could not be replaced."""


class _RoadmapCache:
    """Short-lived copy so opening the modal does not hit COS every time."""

    __slots__ = ("payload", "stored_at")

    def __init__(self) -> None:
        self.payload: Optional[RoadmapDict] = None
        self.stored_at = 0.0


_CACHE = _RoadmapCache()


def clear_product_roadmap_cache() -> None:
    """Drop the in-process copy. Tests and a fresh read use this."""
    _CACHE.payload = None
    _CACHE.stored_at = 0.0


def empty_product_roadmap() -> RoadmapDict:
    """Board shown when the shared object is missing."""
    return {"updated_at": "", "items": []}


def _target(value: object) -> str:
    """Keep a Chinese year-month such as ``2026年12月``. Anything else is blank."""
    text = _clip(value, 16)
    if _TARGET_RE.fullmatch(text):
        return text
    return ""


def _clip(value: object, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _parse_item(row: object) -> Optional[RoadmapItemDict]:
    if not isinstance(row, dict):
        return None
    column = _clip(row.get("column"), 16)
    if column not in _COLUMN_SET:
        return None
    title = _clip(row.get("title"))
    if not title:
        return None
    return {
        "column": column,
        "title": title,
        "summary": _clip(row.get("summary")),
        "owner": _clip(row.get("owner"), 80),
        "area": _clip(row.get("area"), 80),
        "target": _target(row.get("target")),
    }


def parse_product_roadmap(raw: bytes) -> RoadmapDict:
    """Parse the shared JSON. A bad row is skipped. A bad file raises ValueError."""
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("product roadmap is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("product roadmap must be a JSON object")
    rows = payload.get("items", [])
    if not isinstance(rows, list):
        raise ValueError("product roadmap items must be a list")
    items: list[RoadmapItemDict] = []
    for row in rows:
        if len(items) >= _MAX_ITEMS:
            break
        parsed = _parse_item(row)
        if parsed is not None:
            items.append(parsed)
    return {"updated_at": _clip(payload.get("updated_at"), 40), "items": items}


def load_product_roadmap() -> RoadmapDict:
    """Read the shared object. Missing COS or a missing key yields an empty board."""
    now = time.monotonic()
    cached = _CACHE.payload
    if cached is not None and now - _CACHE.stored_at < _CACHE_SECONDS:
        return cached
    raw = get_object_bytes(
        ROADMAP_OBJECT_KEY,
        max_bytes=_MAX_BYTES,
        log_prefix="[Roadmap]",
    )
    if not raw:
        payload = empty_product_roadmap()
    else:
        payload = parse_product_roadmap(raw)
    _CACHE.payload = payload
    _CACHE.stored_at = now
    return payload


def _shanghai_today() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def _remember(payload: RoadmapDict) -> RoadmapDict:
    _CACHE.payload = payload
    _CACHE.stored_at = time.monotonic()
    return payload


def save_product_roadmap(rows: Sequence[object]) -> RoadmapDict:
    """Replace the shared object. A bad row raises ValueError. COS failure raises RoadmapWriteError."""
    if len(rows) > _MAX_ITEMS:
        raise ValueError("product roadmap has too many items")
    items: list[RoadmapItemDict] = []
    for row in rows:
        parsed = _parse_item(row)
        if parsed is None:
            raise ValueError("product roadmap item is invalid")
        items.append(parsed)
    payload: RoadmapDict = {"updated_at": _shanghai_today(), "items": items}
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    stored = upload_bytes(
        body,
        ROADMAP_OBJECT_KEY,
        log_prefix="[Roadmap]",
        content_type="application/json; charset=utf-8",
    )
    if not stored:
        raise RoadmapWriteError("product roadmap upload failed")
    return _remember(payload)
