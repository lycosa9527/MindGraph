"""Try bare hex key verification against WeChat DB salts."""

from __future__ import annotations

from file_reader.win32_ctypes import windll_module
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_wcdb = importlib.import_module("file_reader.wechat.wcdb")
_enum_readable_regions = _wcdb._enum_readable_regions
_read_process_memory = _wcdb._read_process_memory
_weixin_pids = _wcdb._weixin_pids
collect_db_files = _wcdb.collect_db_files
verify_enc_key = _wcdb.verify_enc_key


def main() -> None:
    db_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\rulerwang_c571\db_storage")
    db_files, _salt_to_rels = collect_db_files(db_dir)
    page1_by_salt = {salt: page1 for _r, _p, _s, salt, page1 in db_files}

    bare96 = re.compile(rb"(?<![0-9a-fA-F])([0-9a-fA-F]{96})(?![0-9a-fA-F])")
    bare64 = re.compile(rb"(?<![0-9a-fA-F])([0-9a-fA-F]{64})(?![0-9a-fA-F])")

    found: dict[str, str] = {}
    tried_96 = 0
    tried_64 = 0
    kernel32 = windll_module("kernel32")
    access = 0x0010 | 0x0400

    for pid in _weixin_pids():
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            continue
        try:
            for base, size in _enum_readable_regions(handle):
                data = _read_process_memory(handle, base, size)
                if not data:
                    continue
                for match in bare96.finditer(data):
                    tried_96 += 1
                    hex_str = match.group(1).decode()
                    enc_key_hex = hex_str[:64]
                    salt_hex = hex_str[64:]
                    page1 = page1_by_salt.get(salt_hex)
                    if page1 and verify_enc_key(bytes.fromhex(enc_key_hex), page1):
                        found[salt_hex] = enc_key_hex
                for match in bare64.finditer(data):
                    tried_64 += 1
                    enc_key_hex = match.group(1).decode()
                    enc_key = bytes.fromhex(enc_key_hex)
                    for salt_hex, page1 in page1_by_salt.items():
                        if salt_hex in found:
                            continue
                        if verify_enc_key(enc_key, page1):
                            found[salt_hex] = enc_key_hex
        finally:
            kernel32.CloseHandle(handle)

    print(f"tried bare96={tried_96} bare64={tried_64}")
    print(f"verified salts={len(found)} / {len(page1_by_salt)}")
    for salt, key in list(found.items())[:3]:
        print(f"  salt={salt[:16]}... key={key[:16]}...")


if __name__ == "__main__":
    main()
