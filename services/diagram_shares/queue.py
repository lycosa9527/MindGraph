"""
FIFO open-order for a shared diagram.

The earliest tab still heartbeating is the editor. Later tabs are viewers.
Pure list operations so the order can be tested without Redis.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

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


def prune_tabs(tabs: list[ShareTab], now: float) -> list[ShareTab]:
    """Drop tabs whose heartbeat is older than the lease window."""
    return [tab for tab in tabs if now - tab.seen_at <= LEASE_TTL_SECONDS]


def join_tab(
    tabs: list[ShareTab],
    now: float,
    user_id: int,
    tab_id: str,
    name: str,
) -> list[ShareTab]:
    """Refresh an existing tab in place, or append a new arrival."""
    fresh = prune_tabs(tabs, now)
    for tab in fresh:
        if tab.user_id == user_id and tab.tab_id == tab_id:
            tab.seen_at = now
            tab.name = name or tab.name
            return fresh
    fresh.append(ShareTab(user_id=user_id, tab_id=tab_id, name=name, seen_at=now))
    return fresh


def leave_tab(tabs: list[ShareTab], now: float, user_id: int, tab_id: str) -> list[ShareTab]:
    """Remove one tab and drop stale heartbeats."""
    fresh = prune_tabs(tabs, now)
    return [tab for tab in fresh if not (tab.user_id == user_id and tab.tab_id == tab_id)]


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
