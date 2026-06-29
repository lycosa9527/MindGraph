"""WeChat 4.x WCDB page decryption and decrypted DB cache."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import os
import struct
from pathlib import Path
from typing import Dict, Iterable, Optional

from Crypto.Cipher import AES

from file_reader.wechat.crypto import (
    HMAC_SZ,
    IV_SZ,
    KEY_SZ,
    PAGE_SZ,
    RESERVE_SZ,
    SALT_SZ,
    SQLITE_HDR,
    WeChatKeyError,
    collect_db_files,
    verify_enc_key,
)
from file_reader.wechat.key_extract import extract_db_keys
from file_reader.wechat.v3 import decrypt_v3_database_enc

__all__ = [
    "DecryptedDbCache",
    "PAGE_SZ",
    "WeChatKeyError",
    "collect_db_files",
    "decrypt_database",
    "default_cache_dir",
    "verify_enc_key",
]


def derive_mac_key(enc_key: bytes, salt: bytes) -> bytes:
    """Derive the HMAC key for a SQLCipher page."""
    mac_salt = bytes(byte ^ 0x3A for byte in salt)
    return hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=KEY_SZ)


def decrypt_page(enc_key: bytes, page_data: bytes, page_number: int) -> bytes:
    """Decrypt one SQLCipher page into a plain SQLite page."""
    iv = page_data[PAGE_SZ - RESERVE_SZ : PAGE_SZ - RESERVE_SZ + IV_SZ]
    if page_number == 1:
        encrypted = page_data[SALT_SZ : PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return bytes(bytearray(SQLITE_HDR + decrypted + b"\x00" * RESERVE_SZ))
    encrypted = page_data[: PAGE_SZ - RESERVE_SZ]
    cipher = AES.new(enc_key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(encrypted)
    return decrypted + b"\x00" * RESERVE_SZ


def decrypt_database(source: Path, destination: Path, enc_key: bytes) -> None:
    """Decrypt an encrypted WCDB file to a plain SQLite database."""
    file_size = source.stat().st_size
    total_pages = file_size // PAGE_SZ
    if file_size % PAGE_SZ != 0:
        total_pages += 1

    page1 = source.read_bytes()[:PAGE_SZ]
    if len(page1) < PAGE_SZ:
        raise ValueError("database file is too small")

    salt = page1[:SALT_SZ]
    mac_key = derive_mac_key(enc_key, salt)
    hmac_data = page1[SALT_SZ : PAGE_SZ - RESERVE_SZ + IV_SZ]
    stored_hmac = page1[PAGE_SZ - HMAC_SZ : PAGE_SZ]
    hm = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
    hm.update(struct.pack("<I", 1))
    if hm.digest() != stored_hmac:
        raise ValueError("page 1 HMAC verification failed")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("wb") as writer:
        for page_number in range(1, total_pages + 1):
            page = reader.read(PAGE_SZ)
            if len(page) < PAGE_SZ:
                if len(page) == 0:
                    break
                page = page + b"\x00" * (PAGE_SZ - len(page))
            writer.write(decrypt_page(enc_key, page, page_number))


class DecryptedDbCache:
    """Decrypt-on-demand cache for WeChat WCDB files."""

    def __init__(
        self,
        db_dir: Path,
        cache_dir: Path,
        keys: Optional[Dict[str, str]] = None,
        *,
        client_variant: Optional[str] = None,
        account_dir: Optional[Path] = None,
    ) -> None:
        self._db_dir = db_dir
        self._cache_dir = cache_dir
        self._keys = keys
        self._client_variant = client_variant
        self._account_dir = account_dir

    @property
    def keys(self) -> Dict[str, str]:
        """Lazy-loaded map of db relative path to hex encryption key."""
        if self._keys is None:
            self._keys = extract_db_keys(
                self._db_dir,
                client_variant=self._client_variant,
                account_dir=self._account_dir,
            )
        return self._keys

    def rel_keys(self) -> Iterable[str]:
        """Relative DB paths that have extracted encryption keys."""
        return self.keys.keys()

    def plain_path(self, rel: str) -> Path:
        """Return a decrypted SQLite path for rel (posix-style under db_dir)."""
        enc_key_hex = self.keys.get(rel)
        if not enc_key_hex:
            raise WeChatKeyError(f"No encryption key for {rel}")
        source = self._db_dir / Path(rel)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        destination = self._cache_dir / Path(rel)
        if destination.is_file():
            try:
                if destination.stat().st_mtime >= source.stat().st_mtime:
                    return destination
            except OSError:
                pass
        enc_key = bytes.fromhex(enc_key_hex)
        if self._client_variant == "v3":
            decrypt_v3_database_enc(source, destination, enc_key)
        else:
            decrypt_database(source, destination, enc_key)
        return destination


def default_cache_dir(account_dir: Path) -> Path:
    """Per-account decrypted DB cache under the system temp directory."""
    digest = hashlib.sha256(str(account_dir.resolve()).encode()).hexdigest()[:16]
    return Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))) / "mindgraph-file-reader" / digest
