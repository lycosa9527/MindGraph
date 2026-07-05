"""Unit tests for WeCom key extraction helpers."""

from __future__ import annotations

from pathlib import Path

from file_reader.wecom.discovery import DbFileEntry
from file_reader.wecom.key_extract import _chat_unlock_keys_present


def _db_entry(rel: str, salt_hex: str, page1: bytes) -> DbFileEntry:
    """Build one synthetic ``DbFileEntry`` for unlock-key tests."""
    return rel, Path(rel), 4096, salt_hex, page1


def test_chat_unlock_requires_session_db_key() -> None:
    """Chat unlock needs a session.db key, not only message shard keys."""
    db_files = [
        _db_entry("session/session.db", "aa" * 16, b"\x00" * 16),
        _db_entry("message/message_0.db", "bb" * 16, b"\x00" * 16),
    ]
    assert not _chat_unlock_keys_present(db_files, {"message/message_0.db": "cc" * 16})
    assert _chat_unlock_keys_present(
        db_files,
        {"session/session.db": "dd" * 16, "message/message_0.db": "cc" * 16},
    )


def test_chat_unlock_accepts_flat_session_db() -> None:
    """Flat session.db path satisfies chat unlock requirements."""
    db_files = [
        _db_entry("session.db", "aa" * 16, b"\x00" * 16),
    ]
    assert _chat_unlock_keys_present(db_files, {"session.db": "dd" * 16})


def test_chat_unlock_accepts_plain_session_db() -> None:
    """Unencrypted session.db counts as unlocked without a cached key."""
    db_files = [
        _db_entry(
            "session.db",
            "aa" * 16,
            b"SQLite format 3\x00" + b"\x00" * 4096,
        ),
    ]
    assert _chat_unlock_keys_present(db_files, {})
