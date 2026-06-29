"""Tests for WeCom session listing from decrypted databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from file_reader.wecom.db_reader import WeComDbReader, WeComUserDirectory
from file_reader.wecom.discovery import is_chat_db_rel


class _FakeCache:
    def __init__(self, cache_root: Path) -> None:
        self._cache_root = cache_root

    def ensure_chat_dbs(self) -> Path:
        return self._cache_root


def _write_message_db(
    path: Path,
    conversation_id: str,
    send_time: int,
    *,
    sender_id: int = 1001,
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE message_table (
                conversation_id TEXT,
                sender_id INTEGER,
                content_type INTEGER,
                send_time INTEGER,
                content TEXT,
                extra_content BLOB,
                local_extra_content BLOB,
                message_id INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO message_table (
                conversation_id, sender_id, content_type, send_time, content, message_id
            ) VALUES (?, ?, 2, ?, 'hello', 1)
            """,
            (conversation_id, sender_id, send_time),
        )


def _write_session_db(path: Path, *, with_conversation_table: bool) -> None:
    with sqlite3.connect(path) as conn:
        if not with_conversation_table:
            return
        conn.execute(
            """
            CREATE TABLE conversation_table (
                id TEXT,
                name TEXT,
                roomname_remark TEXT,
                last_message_time INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO conversation_table (id, name, roomname_remark, last_message_time)
            VALUES ('S:1001_2002', 'Alice', '', 0)
            """
        )


def _write_user_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE user_table (
                id INTEGER,
                name TEXT,
                real_name TEXT,
                account TEXT,
                external_corp_name TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE external_user_relation_v3 (
                user_id INTEGER,
                remarks TEXT,
                real_remarks TEXT,
                corp_remark TEXT
            )
            """
        )
        conn.execute("INSERT INTO user_table (id, name, real_name, account) VALUES (2002, 'Bob', '', '')")
        conn.execute(
            """
            INSERT INTO external_user_relation_v3 (user_id, remarks, real_remarks, corp_remark)
            VALUES (2002, 'Bob Remark', '', '')
            """
        )


def _write_group_session_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE conversation_table (
                id TEXT,
                name TEXT,
                roomname_remark TEXT,
                last_message_time INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO conversation_table (id, name, roomname_remark, last_message_time)
            VALUES ('R:100', 'Default Group Name', 'My Group Remark', 1_700_000_000)
            """
        )
        conn.execute(
            """
            CREATE TABLE conversation_user_table (
                conversation_id TEXT,
                user_id INTEGER,
                nick_name TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO conversation_user_table (conversation_id, user_id, nick_name)
            VALUES ('R:100', 2002, 'Group Nick')
            """
        )


def test_is_chat_db_rel_includes_flat_message_shards() -> None:
    assert is_chat_db_rel("message_0.db")
    assert is_chat_db_rel("message/message_1.db")


def test_list_sessions_without_conversation_table_uses_message_db(tmp_path: Path) -> None:
    _write_session_db(tmp_path / "session.db", with_conversation_table=False)
    _write_message_db(tmp_path / "message.db", "S:1001_2002", 1_700_000_000)

    reader = WeComDbReader(_FakeCache(tmp_path), self_id=1001)
    sessions = reader.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].conversation_id == "S:1001_2002"
    assert sessions[0].last_timestamp == 1_700_000_000


def test_list_sessions_merges_flat_message_shard(tmp_path: Path) -> None:
    _write_session_db(tmp_path / "session.db", with_conversation_table=True)
    _write_message_db(tmp_path / "message_0.db", "R:999", 1_700_000_100)

    reader = WeComDbReader(_FakeCache(tmp_path), self_id=1001)
    sessions = reader.list_sessions()

    ids = {session.conversation_id for session in sessions}
    assert "R:999" in ids


def test_group_session_prefers_roomname_remark(tmp_path: Path) -> None:
    _write_group_session_db(tmp_path / "session.db")
    _write_message_db(tmp_path / "message.db", "R:100", 1_700_000_000)

    reader = WeComDbReader(_FakeCache(tmp_path), self_id=1001)
    sessions = reader.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].display_name == "My Group Remark"


def test_group_sender_prefers_remark_over_nick(tmp_path: Path) -> None:
    _write_group_session_db(tmp_path / "session.db")
    _write_user_db(tmp_path / "user.db")
    _write_message_db(tmp_path / "message.db", "R:100", 1_700_000_000, sender_id=2002)

    reader = WeComDbReader(_FakeCache(tmp_path), self_id=1001)
    messages = reader.load_messages("R:100")

    assert len(messages) == 1
    assert messages[0].sender == "Bob Remark"


def test_user_directory_sender_label() -> None:
    directory = WeComUserDirectory(
        remarks={2002: "Bob Remark"},
        display_names={2002: "Bob"},
    )
    member_names = {"R:100": {2002: "Group Nick"}}

    assert directory.sender_label(2002, "R:100", member_names) == "Bob Remark"
