"""DingTalk local database decryption (V2/V3 AES-128-ECB pages).

Ported from dingwave-V3 decrypt.py — see dingtalk/REFERENCES.md.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import Literal, Optional

from Crypto.Cipher import AES

DingTalkStorageVersion = Literal["v2", "v3"]

_PAGE_SIZE = 4096
_SQLITE_HEADER = b"SQLite format 3\x00"
_V3_PBKDF2_SALT = b"666DingTalk888"[:8]
_V3_PBKDF2_ITERATIONS = 1000
_V3_PBKDF2_DKLEN = 32


class DingTalkCryptoError(RuntimeError):
    """Failed to derive a key or decrypt a DingTalk database."""


def generate_key_v2(uid: str) -> bytes:
    """V2: first 16 chars of MD5(uid) hex as ASCII key bytes."""
    digest = hashlib.md5(uid.encode("utf-8")).hexdigest()
    return digest[:16].encode("ascii")


def generate_key_v3(uid: str, salt_hex: str) -> bytes:
    """V3: PBKDF2(uid+salt) then MD5 → first 16 hex chars as key."""
    if not salt_hex.strip():
        raise DingTalkCryptoError("V3 salt is required")
    password = (uid + salt_hex.strip()).encode("utf-8")
    derived = hashlib.pbkdf2_hmac(
        "sha1",
        password,
        _V3_PBKDF2_SALT,
        _V3_PBKDF2_ITERATIONS,
        dklen=_V3_PBKDF2_DKLEN,
    )
    digest = hashlib.md5(derived).hexdigest()
    return digest[:16].encode("ascii")


def generate_key(
    uid: str,
    *,
    version: DingTalkStorageVersion,
    salt_hex: Optional[str] = None,
) -> bytes:
    """Return AES key bytes for the given storage version."""
    if version == "v3":
        if salt_hex is None:
            raise DingTalkCryptoError("V3 salt is required")
        return generate_key_v3(uid, salt_hex)
    return generate_key_v2(uid)


def decrypt_aes_ecb_pages(data: bytes, key: bytes) -> bytes:
    """Decrypt DingTalk DB file data page-by-page."""
    cipher = AES.new(key, AES.MODE_ECB)
    result = bytearray()
    for offset in range(0, len(data), _PAGE_SIZE):
        page = data[offset : offset + _PAGE_SIZE]
        if len(page) == _PAGE_SIZE:
            for block_start in range(0, _PAGE_SIZE, 16):
                block = page[block_start : block_start + 16]
                result.extend(cipher.decrypt(block))
        else:
            result.extend(page)
    return bytes(result)


def decrypt_database_file(
    encrypted_path: Path,
    output_path: Path,
    *,
    uid: str,
    version: DingTalkStorageVersion,
    salt_hex: Optional[str] = None,
) -> Path:
    """Decrypt ``dingtalk.db`` to a plain SQLite file."""
    key = generate_key(uid, version=version, salt_hex=salt_hex)
    encrypted = encrypted_path.read_bytes()
    decrypted = decrypt_aes_ecb_pages(encrypted, key)
    if decrypted[:16] != _SQLITE_HEADER:
        raise DingTalkCryptoError(
            "Decryption failed: output is not a valid SQLite database. Check real_uid and user_config salt."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(decrypted)
    return output_path


def copy_encrypted_db(
    encrypted_path: Path,
    dest_dir: Path,
    *,
    retry_count: int = 3,
    retry_delay_sec: float = 0.5,
) -> Path:
    """Copy encrypted DB (+ wal/shm) to avoid file locks."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_db = dest_dir / encrypted_path.name
    pairs = [
        (encrypted_path, dest_db),
        (Path(str(encrypted_path) + "-wal"), Path(str(dest_db) + "-wal")),
        (Path(str(encrypted_path) + "-shm"), Path(str(dest_db) + "-shm")),
    ]
    last_error: Optional[OSError] = None
    for attempt in range(retry_count):
        try:
            for source, target in pairs:
                if source.is_file():
                    shutil.copy2(source, target)
            return dest_db
        except OSError as exc:
            last_error = exc
            if attempt + 1 < retry_count:
                time.sleep(retry_delay_sec)
    if last_error is not None:
        raise DingTalkCryptoError(f"Could not copy encrypted database: {last_error}") from last_error
    raise DingTalkCryptoError("Could not copy encrypted database")
