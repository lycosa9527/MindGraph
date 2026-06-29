"""Probe WeChat 4.1+ passphrase extraction strategies."""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_wcdb = importlib.import_module("file_reader.wechat.wcdb")
KEY_SZ = _wcdb.KEY_SZ
_enum_readable_regions = _wcdb._enum_readable_regions
_read_process_memory = _wcdb._read_process_memory
_weixin_pids = _wcdb._weixin_pids
collect_db_files = _wcdb.collect_db_files
verify_enc_key = _wcdb.verify_enc_key

ANCHORS = (
    b"com.Tencent.WCDB.Config.Cipher",
    b"WCDB.Config.Cipher",
    b"CipherConfig",
    b"setCipherKey",
)
PBKDF2_ITER = 256000


def _try_passphrase(candidate: bytes, page1: bytes, salt: bytes) -> bool:
    if len(candidate) != KEY_SZ:
        return False
    enc_key = hashlib.pbkdf2_hmac("sha512", candidate, salt, PBKDF2_ITER, dklen=KEY_SZ)
    return verify_enc_key(enc_key, page1)


def _candidates_near(data: bytes, anchor: bytes) -> list[bytes]:
    out: list[bytes] = []
    start = 0
    while True:
        idx = data.find(anchor, start)
        if idx < 0:
            break
        for offset in range(-128, 129, 8):
            pos = idx + offset
            if pos < 0 or pos + KEY_SZ > len(data):
                continue
            out.append(data[pos : pos + KEY_SZ])
        start = idx + 1
    return out


def _candidates_from_key_info(login_dir: Path) -> list[bytes]:
    key_file = login_dir / "key_info.db"
    if not key_file.is_file():
        return []
    out: list[bytes] = []
    conn = sqlite3.connect(key_file)
    try:
        rows = conn.execute("SELECT key_info_data FROM LoginKeyInfoTable").fetchall()
    finally:
        conn.close()
    for (blob,) in rows:
        if not isinstance(blob, (bytes, bytearray)) or len(blob) < KEY_SZ + 24:
            continue
        for offset in (16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60):
            if offset + KEY_SZ <= len(blob):
                out.append(bytes(blob[offset : offset + KEY_SZ]))
    return out


def main() -> None:
    db_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\rulerwang_c571\db_storage")
    login_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\all_users\login\rulerwang")
    db_files, salt_to_rels = collect_db_files(db_dir)
    session_page1 = next(page1 for rel, _p, _s, _salt, page1 in db_files if rel == "session/session.db")
    session_salt = session_page1[:16]

    tried = 0
    seen: set[bytes] = set()
    candidates = _candidates_from_key_info(login_dir)
    print(f"key_info candidates: {len(candidates)}")

    kernel32 = ctypes.windll.kernel32
    access = 0x0010 | 0x0400
    anchor_hits = 0
    for pid in _weixin_pids():
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            continue
        try:
            for base, size in _enum_readable_regions(handle):
                data = _read_process_memory(handle, base, size)
                if not data:
                    continue
                for anchor in ANCHORS:
                    if anchor in data:
                        anchor_hits += 1
                        candidates.extend(_candidates_near(data, anchor))
        finally:
            kernel32.CloseHandle(handle)

    print(f"anchor hits: {anchor_hits}, total candidates: {len(candidates)}")
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        tried += 1
        if _try_passphrase(candidate, session_page1, session_salt):
            print("PASSPHRASE FOUND via PBKDF2:", candidate.hex())
            return
        if tried % 50 == 0:
            print(f"  tried {tried}...")
    print(f"no passphrase after {tried} candidates")


if __name__ == "__main__":
    main()
