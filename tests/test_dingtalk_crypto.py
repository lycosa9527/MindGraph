"""Unit tests for DingTalk crypto helpers."""

from __future__ import annotations

from Crypto.Cipher import AES

from file_reader.dingtalk.crypto import decrypt_aes_ecb_pages, generate_key_v3


def test_generate_key_v3_stable() -> None:
    uid = "123456789"
    salt = "a" * 32
    assert generate_key_v3(uid, salt) == generate_key_v3(uid, salt)
    assert len(generate_key_v3(uid, salt)) == 16


def test_decrypt_aes_ecb_page_header() -> None:
    key = b"0123456789abcdef"
    cipher = AES.new(key, AES.MODE_ECB)
    plain_page = b"SQLite format 3\x00" + b"\x00" * (4096 - 16)
    encrypted = bytearray()
    for start in range(0, 4096, 16):
        encrypted.extend(cipher.encrypt(plain_page[start : start + 16]))
    decrypted = decrypt_aes_ecb_pages(bytes(encrypted), key)
    assert decrypted[:16] == b"SQLite format 3\x00"
