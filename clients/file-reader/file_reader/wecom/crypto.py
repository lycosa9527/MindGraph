"""WeCom wxSQLite3 AES-128-CBC page decryption.

Ported from ylytdeng/wechat-decrypt wxwork_crypto.py — see wecom/REFERENCES.md.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import struct
import time
from pathlib import Path

from Crypto.Cipher import AES

PAGE_SZ = 4096
SALT_SZ = 16
SQLITE_HDR = b"SQLite format 3\x00"
WXSQLITE3_SALT = b"sAlT"


class WeComCryptoError(RuntimeError):
    """Failed to decrypt a WeCom wxSQLite3 database."""


def _modmult(a: int, b: int, c: int, m: int, s: int) -> int:
    quotient = s // a
    state = b * (s - a * quotient) - c * quotient
    if state < 0:
        state += m
    return state


def generate_initial_vector(page_no: int) -> bytes:
    """Match SQLite3MultipleCiphers sqlite3mcGenerateInitialVector()."""
    state = page_no + 1
    initkey = bytearray(16)
    for index in range(4):
        state = _modmult(52774, 40692, 3791, 2147483399, state)
        initkey[index * 4 : index * 4 + 4] = struct.pack("<I", state & 0xFFFFFFFF)
    return hashlib.md5(initkey).digest()


def derive_wxsqlite3_aes128_page_key(raw_key: bytes, page_no: int) -> bytes:
    """Derive the per-page AES-128 key used by wxSQLite3 AES-128-CBC."""
    if len(raw_key) != 16:
        raise WeComCryptoError("wxSQLite3 AES-128 raw key must be 16 bytes")
    material = raw_key + struct.pack("<I", page_no) + WXSQLITE3_SALT
    return hashlib.md5(material).digest()


def is_plain_sqlite_page(page: bytes) -> bool:
    """Return True when page bytes start with the SQLite file magic."""
    return page[: len(SQLITE_HDR)] == SQLITE_HDR


def has_wxsqlite3_plain_header_fragment(page: bytes) -> bool:
    """New wxSQLite3 AES mode keeps SQLite header bytes 16..23 in plaintext."""
    if len(page) < 24:
        return False
    header = page[16:24]
    page_size = (header[0] << 8) | header[1]
    if page_size == 1:
        page_size = 65536
    return (
        512 <= page_size <= 65536
        and (page_size & (page_size - 1)) == 0
        and header[5] == 0x40
        and header[6] == 0x20
        and header[7] == 0x20
    )


def is_wxsqlite3_aes128_page1(page: bytes) -> bool:
    """Return True when page 1 looks like wxSQLite3 AES-128 encryption."""
    return not is_plain_sqlite_page(page) and has_wxsqlite3_plain_header_fragment(page)


def _decrypt_aes128_cbc(raw_key: bytes, page_no: int, data: bytes) -> bytes:
    page_key = derive_wxsqlite3_aes128_page_key(raw_key, page_no)
    init_vector = generate_initial_vector(page_no)
    return AES.new(page_key, AES.MODE_CBC, init_vector).decrypt(data)


def decrypt_wxsqlite3_aes128_page(raw_key: bytes, page_data: bytes, page_no: int) -> bytes:
    """Decrypt one wxSQLite3 AES-128-CBC page to a normal SQLite page."""
    if len(page_data) != PAGE_SZ:
        raise WeComCryptoError(f"page must be exactly {PAGE_SZ} bytes")

    data = bytearray(page_data)
    if page_no == 1 and has_wxsqlite3_plain_header_fragment(data):
        db_header_fragment = bytes(data[16:24])
        data[16:24] = data[8:16]
        decrypted_tail = _decrypt_aes128_cbc(raw_key, page_no, bytes(data[16:]))
        data[16:] = decrypted_tail
        if bytes(data[16:24]) != db_header_fragment:
            raise WeComCryptoError("wxSQLite3 AES-128 key validation failed")
        data[:16] = SQLITE_HDR
        return bytes(data)

    return _decrypt_aes128_cbc(raw_key, page_no, bytes(data))


def looks_like_sqlite_page1(page: bytes) -> bool:
    """Heuristic check for a valid SQLite btree page 1 after decrypt."""
    if page[: len(SQLITE_HDR)] != SQLITE_HDR:
        return False
    if len(page) < 108:
        return False
    btree_page_type = page[100]
    return btree_page_type in (0x02, 0x05, 0x0A, 0x0D)


def verify_wxsqlite3_aes128_key(raw_key: bytes, page1: bytes) -> bool:
    """Return True when ``raw_key`` decrypts wxSQLite3 page 1 successfully."""
    if len(raw_key) != 16 or len(page1) < PAGE_SZ:
        return False
    try:
        decrypted = decrypt_wxsqlite3_aes128_page(raw_key, page1[:PAGE_SZ], 1)
    except (WeComCryptoError, ValueError):
        return False
    return looks_like_sqlite_page1(decrypted)


def decrypt_wxwork_database(db_path: Path, out_path: Path, raw_key: bytes) -> None:
    """Decrypt an encrypted wxSQLite3 database file."""
    size = db_path.stat().st_size
    total_pages = (size + PAGE_SZ - 1) // PAGE_SZ
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("rb") as source, out_path.open("wb") as target:
        for page_no in range(1, total_pages + 1):
            page = source.read(PAGE_SZ)
            if not page:
                break
            if len(page) < PAGE_SZ:
                page += b"\x00" * (PAGE_SZ - len(page))
            target.write(decrypt_wxsqlite3_aes128_page(raw_key, page, page_no))


def verify_sqlite_file(path: Path) -> list[str]:
    """Return table names when a decrypted file is valid SQLite."""
    with sqlite3.connect(str(path)) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [str(row[0]) for row in rows]


def copy_encrypted_db(source: Path, dest_dir: Path, *, retries: int = 4) -> Path:
    """Copy encrypted DB and sidecar WAL/SHM with retries while WXWork holds locks."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            shutil.copy2(source, dest)
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(source) + suffix)
                if sidecar.is_file():
                    shutil.copy2(sidecar, dest_dir / sidecar.name)
            return dest
        except OSError as exc:
            last_error = exc
            time.sleep(0.25 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise OSError(f"failed to copy {source}")
