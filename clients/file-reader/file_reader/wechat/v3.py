"""WeChat 3.x SQLCipher validation and page decryption (Windows).

Ported from github.com/svcvit/chatlog internal/wechat/decrypt/windows/v3.go
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import struct
from pathlib import Path

from Crypto.Cipher import AES

from file_reader.wechat.crypto import IV_SZ, KEY_SZ, PAGE_SZ, SALT_SZ, SQLITE_HDR

_V3_ITER = 64000
_V3_HMAC_SZ = 20
_V3_RESERVE_SZ = 48


def derive_v3_enc_key(passphrase: bytes, salt: bytes) -> bytes:
    """Derive AES key from 32-byte material (PBKDF2-SHA1, 64000 iterations)."""
    return hashlib.pbkdf2_hmac("sha1", passphrase, salt, _V3_ITER, dklen=KEY_SZ)


def derive_v3_mac_key(enc_key: bytes, salt: bytes) -> bytes:
    """Derive the v3 HMAC key for SQLCipher page verification."""
    mac_salt = bytes(byte ^ 0x3A for byte in salt)
    return hashlib.pbkdf2_hmac("sha1", enc_key, mac_salt, 2, dklen=KEY_SZ)


def verify_v3_passphrase(passphrase: bytes, page1: bytes) -> bool:
    """Validate 32-byte key material against a v3 database page 1."""
    if len(passphrase) != KEY_SZ or len(page1) < PAGE_SZ:
        return False
    salt = page1[:SALT_SZ]
    enc_key = derive_v3_enc_key(passphrase, salt)
    mac_key = derive_v3_mac_key(enc_key, salt)
    data_end = PAGE_SZ - _V3_RESERVE_SZ + IV_SZ
    hmac_data = page1[SALT_SZ:data_end]
    stored = page1[data_end : data_end + _V3_HMAC_SZ]
    hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha1)
    hm.update(struct.pack("<I", 1))
    return hm.digest() == stored


def decrypt_v3_page(enc_key: bytes, mac_key: bytes, page_data: bytes, page_number: int) -> bytes:
    """Decrypt one v3 SQLCipher page."""
    del mac_key
    iv = page_data[PAGE_SZ - _V3_RESERVE_SZ : PAGE_SZ - _V3_RESERVE_SZ + IV_SZ]
    if page_number == 1:
        encrypted = page_data[SALT_SZ : PAGE_SZ - _V3_RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return bytes(bytearray(SQLITE_HDR + decrypted + b"\x00" * _V3_RESERVE_SZ))
    encrypted = page_data[: PAGE_SZ - _V3_RESERVE_SZ]
    cipher = AES.new(enc_key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(encrypted)
    return decrypted + b"\x00" * _V3_RESERVE_SZ


def decrypt_v3_database(source: Path, destination: Path, passphrase: bytes) -> None:
    """Decrypt a v3 encrypted DB using 32-byte key material."""
    page1 = source.read_bytes()[:PAGE_SZ]
    if len(page1) < PAGE_SZ:
        raise ValueError("database file is too small")
    salt = page1[:SALT_SZ]
    enc_key = derive_v3_enc_key(passphrase, salt)
    if not verify_v3_passphrase(passphrase, page1):
        raise ValueError("v3 page 1 HMAC verification failed")
    decrypt_v3_database_enc(source, destination, enc_key)


def decrypt_v3_database_enc(source: Path, destination: Path, enc_key: bytes) -> None:
    """Decrypt a v3 encrypted DB using a derived AES key."""
    page1 = source.read_bytes()[:PAGE_SZ]
    if len(page1) < PAGE_SZ:
        raise ValueError("database file is too small")
    salt = page1[:SALT_SZ]
    mac_key = derive_v3_mac_key(enc_key, salt)
    data_end = PAGE_SZ - _V3_RESERVE_SZ + IV_SZ
    hmac_data = page1[SALT_SZ:data_end]
    stored = page1[data_end : data_end + _V3_HMAC_SZ]
    hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha1)
    hm.update(struct.pack("<I", 1))
    if hm.digest() != stored:
        raise ValueError("v3 page 1 HMAC verification failed")

    file_size = source.stat().st_size
    total_pages = file_size // PAGE_SZ
    if file_size % PAGE_SZ != 0:
        total_pages += 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("wb") as writer:
        for page_number in range(1, total_pages + 1):
            page = reader.read(PAGE_SZ)
            if len(page) < PAGE_SZ:
                if len(page) == 0:
                    break
                page = page + b"\x00" * (PAGE_SZ - len(page))
            writer.write(decrypt_v3_page(enc_key, mac_key, page, page_number))
