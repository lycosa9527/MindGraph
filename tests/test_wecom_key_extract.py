"""Unit tests for WeCom key extraction helpers."""

from __future__ import annotations

from file_reader.wecom.key_extract import _chat_unlock_keys_present


def test_chat_unlock_requires_session_db_key() -> None:
    db_files = [
        ("session/session.db", None, 4096, "aa" * 16, b"\x00" * 16),
        ("message/message_0.db", None, 4096, "bb" * 16, b"\x00" * 16),
    ]
    assert not _chat_unlock_keys_present(db_files, {"message/message_0.db": "cc" * 16})
    assert _chat_unlock_keys_present(
        db_files,
        {"session/session.db": "dd" * 16, "message/message_0.db": "cc" * 16},
    )


def test_chat_unlock_accepts_flat_session_db() -> None:
    db_files = [
        ("session.db", None, 4096, "aa" * 16, b"\x00" * 16),
    ]
    assert _chat_unlock_keys_present(db_files, {"session.db": "dd" * 16})


def test_chat_unlock_accepts_plain_session_db() -> None:
    db_files = [
        (
            "session.db",
            None,
            4096,
            "aa" * 16,
            b"SQLite format 3\x00" + b"\x00" * 4096,
        ),
    ]
    assert _chat_unlock_keys_present(db_files, {})
