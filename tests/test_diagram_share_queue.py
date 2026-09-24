"""FIFO edit order and share-set diffs for org library sharing."""

from __future__ import annotations

from pytest import MonkeyPatch

from services.diagram_shares.access import items_missing_share_role, share_membership_delta
from services.diagram_shares.fanout import build_share_fanout_body, parse_share_fanout_body
from services.diagram_shares.queue import drop_user_tabs, join_tab, leave_tab, prune_tabs, tab_status


def test_first_open_edits_and_later_open_is_viewer() -> None:
    """Whoever opens first keeps edit rights, including a second tab of the same user."""
    tabs = join_tab([], 100.0, 1, "tab-owner", "Ada")
    tabs = join_tab(tabs, 101.0, 2, "tab-peer", "Bo")
    tabs = join_tab(tabs, 102.0, 1, "tab-owner-2", "Ada")
    assert tab_status(tabs, 1, "tab-owner")["role"] == "editor"
    assert tab_status(tabs, 2, "tab-peer")["role"] == "viewer"
    assert tab_status(tabs, 1, "tab-owner-2")["role"] == "viewer"
    assert tab_status(tabs, 1, "tab-owner")["viewer_count"] == 2
    assert tab_status(tabs, 2, "tab-peer")["editor_name"] == "Ada"


def test_leave_promotes_the_next_opener() -> None:
    """Closing the editor hands edit rights to the next person already open."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada")
    tabs = join_tab(tabs, 101.0, 2, "tab-b", "Bo")
    tabs = join_tab(tabs, 102.0, 3, "tab-c", "Cy")
    tabs = leave_tab(tabs, 103.0, 1, "tab-a")
    assert tab_status(tabs, 2, "tab-b")["role"] == "editor"
    assert tab_status(tabs, 3, "tab-c")["role"] == "viewer"
    assert tab_status(tabs, 3, "tab-c")["editor_name"] == "Bo"


def test_stale_heartbeat_drops_the_editor() -> None:
    """A tab that stops heartbeating loses its place."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada")
    tabs = join_tab(tabs, 101.0, 2, "tab-b", "Bo")
    fresh = prune_tabs(tabs, 100.0 + 31)
    assert tab_status(fresh, 2, "tab-b")["role"] == "editor"


def test_refresh_keeps_arrival_order() -> None:
    """Heartbeats do not move a tab to the back of the queue."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada")
    tabs = join_tab(tabs, 110.0, 2, "tab-b", "Bo")
    tabs = join_tab(tabs, 120.0, 1, "tab-a", "Ada")
    assert tabs[0].tab_id == "tab-a"
    assert tabs[0].seen_at == 120.0


def test_replace_set_removes_unchecked_people() -> None:
    """Saving the dialog drops people who were unchecked and adds new ones."""
    added, removed = share_membership_delta({2, 3}, {3, 4})
    assert added == {4}
    assert removed == {2}


def test_revoked_user_loses_edit_rights() -> None:
    """Removing someone from the share set promotes the next opener."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada")
    tabs = join_tab(tabs, 101.0, 2, "tab-b", "Bo")
    fresh = drop_user_tabs(tabs, 102.0, 1)
    assert tab_status(fresh, 2, "tab-b")["role"] == "editor"


def test_fanout_envelope_round_trip(monkeypatch: MonkeyPatch) -> None:
    """Workers accept only envelopes stamped with the shared origin secret."""
    monkeypatch.setenv("COLLAB_FANOUT_ORIGIN_SECRET", "share-secret")
    raw = build_share_fanout_body("diagram-1", "tab-owner", '{"type":"spec"}')
    assert parse_share_fanout_body(raw) == ("diagram-1", "tab-owner", '{"type":"spec"}')
    assert parse_share_fanout_body(raw.replace("share-secret", "other-secret")) is None


def test_cached_list_without_share_role_is_stale() -> None:
    """Library caches from before sharing must be reloaded."""
    assert items_missing_share_role([{"id": "a"}]) is True
    assert items_missing_share_role([{"id": "a", "share_role": "owner"}]) is False
