"""Unit tests for WeCom wxSQLite3 crypto helpers."""

from __future__ import annotations

from file_reader.wecom.crypto import (
    derive_wxsqlite3_aes128_page_key,
    generate_initial_vector,
    verify_wxsqlite3_aes128_key,
)


def test_derive_page_key_stable() -> None:
    raw_key = b"0123456789abcdef"
    assert derive_wxsqlite3_aes128_page_key(raw_key, 1) == derive_wxsqlite3_aes128_page_key(raw_key, 1)
    assert len(derive_wxsqlite3_aes128_page_key(raw_key, 1)) == 16


def test_generate_initial_vector_changes_with_page() -> None:
    first = generate_initial_vector(1)
    second = generate_initial_vector(2)
    assert first != second
    assert len(first) == 16


def test_verify_rejects_wrong_key() -> None:
    wrong_key = b"fedcba9876543210"
    encrypted = b"\x00" * 16 + b"\x00\x10\x00\x01\x01\x40\x20\x20" + (b"\x01" * (4096 - 24))
    assert verify_wxsqlite3_aes128_key(wrong_key, encrypted) is False
