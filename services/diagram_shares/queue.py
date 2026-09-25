"""
FIFO open-order for a shared diagram.

The earliest open tab is the editor. Later tabs are viewers.
The Redis TTL is only a backstop when the server process dies. A closed
browser tab leaves through its SSE connection, not by waiting out this window.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, TypedDict

from services.utils.error_types import JSON_PARSE_ERRORS

LEASE_TTL_SECONDS = 30


class ShareTabStatus(TypedDict):
    """Role of one tab in the edit queue."""

    role: str
    editor_name: str
    viewer_count: int
    present: bool


@dataclass
class ShareTab:
    """One open canvas tab waiting in arrival order."""

    user_id: int
    tab_id: str
    name: str
    seen_at: float
    epoch: int = 0
    stream: int = 0


def prune_tabs(tabs: list[ShareTab], now: float) -> list[ShareTab]:
    """Drop tabs the server has not refreshed within the lease window."""
    return [tab for tab in tabs if now - tab.seen_at <= LEASE_TTL_SECONDS]


def encode_tabs(tabs: list[ShareTab]) -> str:
    """JSON form stored in Redis and sent on the roster fan-out."""
    return json.dumps(
        [
            {
                "user_id": tab.user_id,
                "tab_id": tab.tab_id,
                "name": tab.name,
                "seen_at": tab.seen_at,
                "epoch": tab.epoch,
                "stream": tab.stream,
            }
            for tab in tabs
        ]
    )


def decode_tabs(text: str) -> list[ShareTab]:
    """Parse a roster or Redis queue. Unusable payloads become an empty queue."""
    try:
        payload = json.loads(text)
    except JSON_PARSE_ERRORS:
        return []
    if not isinstance(payload, list):
        return []
    tabs: list[ShareTab] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            tabs.append(
                ShareTab(
                    user_id=int(item["user_id"]),
                    tab_id=str(item["tab_id"]),
                    name=str(item.get("name") or ""),
                    seen_at=float(item["seen_at"]),
                    epoch=int(item.get("epoch") or 0),
                    stream=int(item.get("stream") or 0),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tabs


def join_tab(
    tabs: list[ShareTab],
    now: float,
    user_id: int,
    tab_id: str,
    name: str,
    epoch: int,
    stream: int = 0,
) -> list[ShareTab]:
    """Refresh an existing tab in place, or append a new arrival.

    A newer page epoch wins. A stale connection cannot take the slot back.
    """
    fresh = prune_tabs(tabs, now)
    for tab in fresh:
        if tab.user_id != user_id or tab.tab_id != tab_id:
            continue
        if epoch < tab.epoch:
            return fresh
        tab.seen_at = now
        tab.name = name or tab.name
        tab.epoch = epoch
        tab.stream = stream
        return fresh
    fresh.append(
        ShareTab(
            user_id=user_id,
            tab_id=tab_id,
            name=name,
            seen_at=now,
            epoch=epoch,
            stream=stream,
        )
    )
    return fresh


def leave_tab(
    tabs: list[ShareTab],
    now: float,
    user_id: int,
    tab_id: str,
    epoch: int,
    stream: Optional[int] = None,
) -> list[ShareTab]:
    """Remove one SSE connection, or the whole page when ``stream`` is omitted."""
    fresh = prune_tabs(tabs, now)

    def matches(tab: ShareTab) -> bool:
        if tab.user_id != user_id or tab.tab_id != tab_id or tab.epoch != epoch:
            return False
        if stream is None:
            return True
        return tab.stream == stream

    return [tab for tab in fresh if not matches(tab)]


def touch_tab(
    tabs: list[ShareTab],
    now: float,
    user_id: int,
    tab_id: str,
    epoch: int,
    stream: int,
) -> tuple[list[ShareTab], str]:
    """Refresh one live connection.

    ``replaced`` when a newer page or stream owns the tab. ``missing`` when it is gone.
    """
    fresh = prune_tabs(tabs, now)
    for tab in fresh:
        if tab.user_id != user_id or tab.tab_id != tab_id:
            continue
        if tab.epoch != epoch or tab.stream != stream:
            return fresh, "replaced"
        tab.seen_at = now
        return fresh, "ok"
    return fresh, "missing"


def drop_user_tabs(tabs: list[ShareTab], now: float, user_id: int) -> list[ShareTab]:
    """Remove every tab belonging to a user who lost library access."""
    fresh = prune_tabs(tabs, now)
    return [tab for tab in fresh if tab.user_id != user_id]


def tab_status(tabs: list[ShareTab], user_id: int, tab_id: str) -> ShareTabStatus:
    """Role of this tab, the editor's name, and how many viewers are waiting."""
    if not tabs:
        return {"role": "editor", "editor_name": "", "viewer_count": 0, "present": False}
    head = tabs[0]
    present = any(tab.user_id == user_id and tab.tab_id == tab_id for tab in tabs)
    role = "editor" if head.user_id == user_id and head.tab_id == tab_id else "viewer"
    return {
        "role": role,
        "editor_name": head.name,
        "viewer_count": max(0, len(tabs) - 1),
        "present": present,
    }


def head_tab(tabs: list[ShareTab]) -> ShareTab | None:
    """The tab that currently holds edit rights."""
    if not tabs:
        return None
    return tabs[0]
