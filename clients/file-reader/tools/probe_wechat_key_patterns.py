"""Count WCDB key patterns in Weixin.exe memory."""

from __future__ import annotations

from file_reader.win32_ctypes import windll_module
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from file_reader.wechat.crypto import collect_db_files
from file_reader.wechat.key_extract import extract_db_keys
from file_reader.wechat.scan_common import (
    build_key_index,
    cross_verify_keys,
    enum_readable_regions,
    read_process_memory,
    scan_memory_for_keys,
)


def _weixin_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=8,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    pids: list[int] = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            try:
                pids.append(int(parts[1]))
            except ValueError:
                continue
    return pids


def main() -> None:
    db_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\rulerwang_c571\db_storage")
    db_files, salt_to_rels = collect_db_files(db_dir)
    hex_pattern = re.compile(rb"x'([0-9a-fA-F]{64,192})'")
    bare_pattern = re.compile(rb"(?<![0-9a-fA-F])([0-9a-fA-F]{96})(?![0-9a-fA-F])")

    wrapped = 0
    bare = 0
    key_map: dict[str, str] = {}
    remaining = set(salt_to_rels.keys())
    kernel32 = windll_module("kernel32")
    access = 0x0010 | 0x0400

    for pid in _weixin_pids():
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            continue
        try:
            for base, size in enum_readable_regions(handle):
                data = read_process_memory(handle, base, size)
                if not data:
                    continue
                wrapped += len(hex_pattern.findall(data))
                bare += len(bare_pattern.findall(data))
                scan_memory_for_keys(data, hex_pattern, db_files, key_map, remaining)
        finally:
            kernel32.CloseHandle(handle)

    cross_verify_keys(db_files, salt_to_rels, key_map)
    indexed = build_key_index(db_files, key_map)
    print(f"x'...' pattern hits: {wrapped}")
    print(f"bare 96-hex hits: {bare}")
    print(f"verified keys: {len(indexed)} / {len(db_files)}")
    print(f"salts matched: {len(key_map)} / {len(salt_to_rels)}")
    try:
        keys = extract_db_keys(db_dir)
        print(f"extract_db_keys OK: {len(keys)} keys")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"extract_db_keys FAIL: {exc}")


if __name__ == "__main__":
    main()
