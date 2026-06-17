"""Unit tests for in-memory workshop editor map merge helpers (Redis layer uses these)."""

from __future__ import annotations

from services.online_collab.participant.online_collab_ws_editor_redis import (
    merge_node_editor_delta_into_document,
    parse_editors_raw,
    purge_user_from_editor_document,
)


def test_merge_node_editor_delta_adds_user() -> None:
    """Test merge node editor delta adds user."""
    editors: dict[str, dict[int, str]] = {}
    merge_node_editor_delta_into_document(editors, "n1", 7, True, "alice")
    assert editors == {"n1": {7: "alice"}}


def test_merge_node_editor_delta_removes_user() -> None:
    """Test merge node editor delta removes user."""
    editors = {"n1": {7: "alice", 9: "bob"}}
    merge_node_editor_delta_into_document(editors, "n1", 7, False, "")
    assert editors == {"n1": {9: "bob"}}


def test_merge_node_editor_delta_drops_empty_node() -> None:
    """Test merge node editor delta drops empty node."""
    editors = {"n1": {7: "alice"}}
    merge_node_editor_delta_into_document(editors, "n1", 7, False, "")
    assert not editors


def test_purge_user_from_editor_document_returns_touched() -> None:
    """Test purge user from editor document returns touched."""
    editors = {"a": {1: "u1", 2: "u2"}, "b": {1: "only"}}
    touched = purge_user_from_editor_document(editors, 1)
    assert set(touched) == {"a", "b"}
    assert editors == {"a": {2: "u2"}}


def test_parse_editors_raw_empty() -> None:
    """Test parse editors raw empty."""
    assert not parse_editors_raw(None)
    assert not parse_editors_raw(b"")
