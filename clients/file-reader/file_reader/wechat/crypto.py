"""WeChat SQLCipher constants and v4 key validation."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import os
import struct
from pathlib import Path
from typing import Dict, List, Tuple

PAGE_SZ = 4096
KEY_SZ = 32
SALT_SZ = 16
IV_SZ = 16
HMAC_SZ = 64
RESERVE_SZ = 80
SQLITE_HDR = b"SQLite format 3\x00"
_PBKDF2_ITER = 256000


class WeChatKeyError(RuntimeError):
    """Raised when WCDB encryption keys cannot be extracted."""


def verify_enc_key(enc_key: bytes, db_page1: bytes) -> bool:
    """Validate a derived encryption key against SQLCipher page 1 HMAC."""
    salt = db_page1[:SALT_SZ]
    mac_salt = bytes(byte ^ 0x3A for byte in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=KEY_SZ)
    hmac_data = db_page1[SALT_SZ : PAGE_SZ - RESERVE_SZ + IV_SZ]
    stored_hmac = db_page1[PAGE_SZ - HMAC_SZ : PAGE_SZ]
    hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
    hm.update(struct.pack("<I", 1))
    return hm.digest() == stored_hmac


def verify_passphrase(passphrase: bytes, db_page1: bytes) -> bool:
    """Validate a 32-byte WCDB passphrase (WeChat 4.1+ memory layout)."""
    if len(passphrase) != KEY_SZ:
        return False
    salt = db_page1[:SALT_SZ]
    enc_key = hashlib.pbkdf2_hmac("sha512", passphrase, salt, _PBKDF2_ITER, dklen=KEY_SZ)
    return verify_enc_key(enc_key, db_page1)


def derive_enc_key_from_passphrase(passphrase: bytes, salt: bytes) -> bytes:
    """Derive the per-database AES key from a WCDB passphrase."""
    return hashlib.pbkdf2_hmac("sha512", passphrase, salt, _PBKDF2_ITER, dklen=KEY_SZ)


def collect_db_files(db_dir: Path) -> Tuple[List[Tuple[str, Path, int, str, bytes]], Dict[str, List[str]]]:
    """Collect encrypted .db files and their salts under db_dir."""
    db_files: List[Tuple[str, Path, int, str, bytes]] = []
    salt_to_rels: Dict[str, List[str]] = {}
    for root, _dirs, files in os.walk(db_dir):
        for name in files:
            if not name.endswith(".db") or name.endswith("-wal") or name.endswith("-shm"):
                continue
            path = Path(root) / name
            size = path.stat().st_size
            if size < PAGE_SZ:
                continue
            page1 = path.read_bytes()[:PAGE_SZ]
            rel = path.relative_to(db_dir).as_posix()
            salt = page1[:SALT_SZ].hex()
            db_files.append((rel, path, size, salt, page1))
            salt_to_rels.setdefault(salt, []).append(rel)
    return db_files, salt_to_rels
