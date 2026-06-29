"""Tests for WeCom discovery path helpers."""

from __future__ import annotations

from file_reader.wecom.discovery import is_chat_db_rel, is_session_db_rel


def test_session_db_rel_flat_and_nested() -> None:
    assert is_session_db_rel("session.db")
    assert is_session_db_rel("session/session.db")
    assert not is_session_db_rel("calendar_r7.db")


def test_chat_db_rel_excludes_calendar() -> None:
    assert is_chat_db_rel("message.db")
    assert is_chat_db_rel("user.db")
    assert not is_chat_db_rel("calendar_r7.db")
    assert not is_chat_db_rel("avatar_store_v3.db")
