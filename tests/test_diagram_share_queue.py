"""FIFO edit order and share-set diffs for org library sharing."""

from __future__ import annotations

from pytest import MonkeyPatch

from services.diagram_shares.access import items_missing_share_role, share_membership_delta
from services.diagram_shares.fanout import (
    build_share_control_body,
    build_share_fanout_body,
    build_share_roster_body,
    parse_share_fanout_body,
    parse_share_fanout_message,
)
from services.diagram_shares.queue import (
    decode_tabs,
    drop_user_tabs,
    encode_tabs,
    join_tab,
    leave_tab,
    prune_tabs,
    tab_status,
    touch_tab,
)


def test_first_open_edits_and_later_open_is_viewer() -> None:
    """Whoever opens first keeps edit rights, including a second tab of the same user."""
    tabs = join_tab([], 100.0, 1, "tab-owner", "Ada", 1)
    tabs = join_tab(tabs, 101.0, 2, "tab-peer", "Bo", 1)
    tabs = join_tab(tabs, 102.0, 1, "tab-owner-2", "Ada", 1)
    assert tab_status(tabs, 1, "tab-owner")["role"] == "editor"
    assert tab_status(tabs, 2, "tab-peer")["role"] == "viewer"
    assert tab_status(tabs, 1, "tab-owner-2")["role"] == "viewer"
    assert tab_status(tabs, 1, "tab-owner")["viewer_count"] == 2
    assert tab_status(tabs, 2, "tab-peer")["editor_name"] == "Ada"


def test_leave_promotes_the_next_opener() -> None:
    """Closing the editor hands edit rights to the next person already open."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1)
    tabs = join_tab(tabs, 101.0, 2, "tab-b", "Bo", 1)
    tabs = join_tab(tabs, 102.0, 3, "tab-c", "Cy", 1)
    tabs = leave_tab(tabs, 103.0, 1, "tab-a", 1)
    assert tab_status(tabs, 2, "tab-b")["role"] == "editor"
    assert tab_status(tabs, 3, "tab-c")["role"] == "viewer"
    assert tab_status(tabs, 3, "tab-c")["editor_name"] == "Bo"


def test_stale_tab_drops_the_editor() -> None:
    """A tab the server has not refreshed loses its place."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1)
    tabs = join_tab(tabs, 101.0, 2, "tab-b", "Bo", 1)
    fresh = prune_tabs(tabs, 100.0 + 31)
    assert tab_status(fresh, 2, "tab-b")["role"] == "editor"


def test_refresh_keeps_arrival_order() -> None:
    """Heartbeats do not move a tab to the back of the queue."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1)
    tabs = join_tab(tabs, 110.0, 2, "tab-b", "Bo", 1)
    tabs = join_tab(tabs, 120.0, 1, "tab-a", "Ada", 2)
    assert tabs[0].tab_id == "tab-a"
    assert tabs[0].seen_at == 120.0


def test_refresh_leave_does_not_drop_the_new_page() -> None:
    """A closing page's leave must not remove the reloaded page that already joined."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1)
    tabs = join_tab(tabs, 101.0, 1, "tab-a", "Ada", 2)
    tabs = leave_tab(tabs, 102.0, 1, "tab-a", 1)
    assert tab_status(tabs, 1, "tab-a")["role"] == "editor"
    assert tabs[0].epoch == 2


def test_replace_set_removes_unchecked_people() -> None:
    """Saving the dialog drops people who were unchecked and adds new ones."""
    added, removed = share_membership_delta({2, 3}, {3, 4})
    assert added == {4}
    assert removed == {2}


def test_revoked_user_loses_edit_rights() -> None:
    """Removing someone from the share set promotes the next opener."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1)
    tabs = join_tab(tabs, 101.0, 2, "tab-b", "Bo", 1)
    fresh = drop_user_tabs(tabs, 102.0, 1)
    assert tab_status(fresh, 2, "tab-b")["role"] == "editor"


def test_fanout_envelope_round_trip(monkeypatch: MonkeyPatch) -> None:
    """Workers accept only envelopes stamped with the shared origin secret."""
    monkeypatch.setenv("COLLAB_FANOUT_ORIGIN_SECRET", "share-secret")
    raw = build_share_fanout_body("diagram-1", "tab-owner", '{"type":"spec"}')
    parsed = parse_share_fanout_message(raw)
    assert parsed is not None
    assert parsed["worker"]
    assert parse_share_fanout_body(raw) == ("diagram-1", "tab-owner", '{"type":"spec"}')
    assert parse_share_fanout_body(raw.replace("share-secret", "other-secret")) is None


def test_fanout_kick_is_not_a_spec(monkeypatch: MonkeyPatch) -> None:
    """A revoke closes sockets. It must not be delivered as a diagram snapshot."""
    monkeypatch.setenv("COLLAB_FANOUT_ORIGIN_SECRET", "share-secret")
    raw = build_share_control_body("diagram-1", "kick", 7)
    message = parse_share_fanout_message(raw)
    assert message is not None
    assert message["action"] == "kick"
    assert message["diagram_id"] == "diagram-1"
    assert message["user_id"] == 7
    assert parse_share_fanout_body(raw) is None
    assert parse_share_fanout_message(raw.replace("share-secret", "other-secret")) is None


def test_reconnect_leave_keeps_the_new_stream() -> None:
    """An old SSE finally must not remove the connection that replaced it."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1, stream=1)
    tabs = join_tab(tabs, 101.0, 1, "tab-a", "Ada", 1, stream=2)
    tabs = leave_tab(tabs, 102.0, 1, "tab-a", 1, stream=1)
    assert len(tabs) == 1
    assert tabs[0].stream == 2
    assert tab_status(tabs, 1, "tab-a")["role"] == "editor"


def test_touch_of_an_old_stream_does_not_refresh_the_new_one() -> None:
    """A replaced connection cannot extend the lease of the live one."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1, stream=2)
    fresh, kind = touch_tab(tabs, 110.0, 1, "tab-a", 1, stream=1)
    assert kind == "replaced"
    assert fresh[0].stream == 2
    assert fresh[0].seen_at == 100.0


def test_older_page_cannot_take_the_slot_back() -> None:
    """A closing page's reconnect must not overwrite the reloaded page."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 2, stream=2)
    tabs = join_tab(tabs, 101.0, 1, "tab-a", "Ada", 1, stream=1)
    assert tabs[0].epoch == 2
    assert tabs[0].stream == 2
    fresh, kind = touch_tab(tabs, 102.0, 1, "tab-a", 1, stream=1)
    assert kind == "replaced"
    assert fresh[0].epoch == 2
    assert fresh[0].seen_at == 100.0


def test_page_leave_drops_every_stream() -> None:
    """Unloading the page drops the tab even if a stream id is still open."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 1, stream=2)
    assert leave_tab(tabs, 101.0, 1, "tab-a", 1) == []


def test_roster_round_trip_keeps_stream() -> None:
    """The stream id has to survive Redis so a reconnect can tell connections apart."""
    tabs = join_tab([], 100.0, 1, "tab-a", "Ada", 4, stream=9)
    restored = decode_tabs(encode_tabs(tabs))
    assert restored[0].epoch == 4
    assert restored[0].stream == 9


def test_fanout_roster_is_not_a_spec(monkeypatch: MonkeyPatch) -> None:
    """Role changes are roster events, not diagram snapshots."""
    monkeypatch.setenv("COLLAB_FANOUT_ORIGIN_SECRET", "share-secret")
    raw = build_share_roster_body("diagram-1", "[]")
    message = parse_share_fanout_message(raw)
    assert message is not None
    assert message["action"] == "roster"
    assert message["body"] == "[]"
    assert parse_share_fanout_body(raw) is None


def test_cached_list_without_share_role_is_stale() -> None:
    """Library caches from before sharing must be reloaded."""
    assert items_missing_share_role([{"id": "a"}]) is True
    assert items_missing_share_role([{"id": "a", "share_role": "owner"}]) is False
